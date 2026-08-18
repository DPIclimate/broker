"""Receive ICT MQTT CSV messages and publish them in IoTa format.

The MQTT worker only validates and writes messages to the disk cache. The
physical-device worker owns the database device maps and RabbitMQ connection.
Consequently, database and RabbitMQ outages do not stop MQTT ingestion.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import logging
import os
import random
import signal
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

import dateutil.parser
import paho.mqtt.client as mqtt
import pika
from pika.exchange_type import ExchangeType

import BrokerConstants
import util.LoggingUtil as lu
from receiver.ict_mqtt.fields import (
    DEVICE_LAYOUT_MAP,
    FIELD_MAPPINGS,
    Field,
    FieldMappingError,
    field_mapping_for_device,
    translate_cache_fields,
    validate_field_mappings,
)


SOURCE = "ict_mqtt"
LEGACY_SOURCE = BrokerConstants.ICT_EAGLEIO
TOPIC_FILTER = "ict/data/+"
ROUTING_KEY = "physical_timeseries"
LAST_CORRELATION_ID = "last_correlation_id"

# Generated from doc/ict_mqtt/pd_map.json. This startup allowlist lets MQTT
# ingestion work before the first database connection. The device worker
# replaces its richer PhysicalDevice map with current database records later.
ICT_EAGLEIO_DEVICE_NAMES = frozenset({
    "mncm1k708", "mncm2l301", "mncm2l302",
    "mncm2l303", "mncm2l304", "mncm2l305", "mncm2l306", "mncm2l307",
    "mncm2l308", "mncm2l309", "mncm2l30a", "mncm2l30b", "mncm2l30c",
    "mncm3lb0c", "mncm3lb0d", "mncm3lb0e", "mncm3lb0f",
    "mncm3m805", "mncm3m806", "mncm3m807", "mncm3p101", "mncm3p102",
    "mncm4lb0c", "mncm4lb0e", "mncm4p101",
})


class ConfigurationError(RuntimeError):
    """The process environment does not contain a valid configuration."""


class InvalidMessage(ValueError):
    """An MQTT or cached message is not safe to process."""


@dataclass(frozen=True)
class Config:
    mqtt_server: str
    mqtt_port: int
    mqtt_keepalive: int
    cache_dir: Path
    test_mode: bool
    test_message_dir: Path | None
    amqp_url: str | None

    @classmethod
    def from_environment(cls) -> "Config":
        server = os.getenv("ICT_MQTT_SERVER")
        if not server:
            raise ConfigurationError("ICT_MQTT_SERVER is required")
        cache_dir_value = os.getenv("ICT_MQTT_DISK_CACHE_DIR")
        if not cache_dir_value:
            raise ConfigurationError("ICT_MQTT_DISK_CACHE_DIR is required")
        test_mode = bool(os.getenv("ICT_MQTT_TEST", "").strip())
        test_message_dir_value = os.getenv("ICT_TEST_MSG_DIR")
        if test_mode and not test_message_dir_value:
            raise ConfigurationError("ICT_TEST_MSG_DIR is required in test mode")
        return cls(
            mqtt_server=server,
            mqtt_port=_positive_int("ICT_MQTT_PORT", 1883),
            mqtt_keepalive=_positive_int("ICT_MQTT_KEEPALIVE", 60),
            cache_dir=Path(cache_dir_value),
            test_mode=test_mode,
            test_message_dir=Path(test_message_dir_value) if test_message_dir_value else None,
            amqp_url=None if test_mode else _amqp_url(),
        )


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer") from error
    if value < 1:
        raise ConfigurationError(f"{name} must be positive")
    return value


def _amqp_url() -> str:
    if value := os.getenv("RABBITMQ_URL"):
        return value
    required = ("RABBITMQ_DEFAULT_USER", "RABBITMQ_DEFAULT_PASS", "RABBITMQ_HOST", "RABBITMQ_PORT")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise ConfigurationError(f"Missing RabbitMQ settings: {', '.join(missing)}")
    user = quote(os.environ[required[0]], safe="")
    password = quote(os.environ[required[1]], safe="")
    return f"amqp://{user}:{password}@{os.environ[required[2]]}:{int(os.environ[required[3]])}/%2F"


def retry_delay(failures: int) -> float:
    """Return an immediate first retry, then 60 seconds with jitter."""
    return 0.0 if failures == 1 else 60.0 + random.uniform(0, 10)


def device_name_from_topic(topic: str) -> str:
    parts = topic.split("/")
    if len(parts) != 3 or parts[:2] != ["ict", "data"] or not parts[2]:
        raise InvalidMessage(f"unexpected MQTT topic {topic!r}")
    return parts[2]


def normalize_timestamp(value: str) -> dt.datetime:
    """Parse a timestamp, treating timestamps without an offset as UTC."""
    try:
        parsed = dt.datetime.fromisoformat(value.strip())
    except ValueError as error:
        raise InvalidMessage(f"Invalid timestamp {value!r}") from error
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=dt.timezone.utc)


@dataclass(frozen=True)
class CachedMessage:
    correlation_id: str
    device_name: str
    values: tuple[str, ...]

    @property
    def timestamp(self) -> dt.datetime:
        return dateutil.parser.isoparse(self.values[0])

    def raw_message(self) -> dict[str, Any]:
        """Return the JSON object stored for the unconverted MQTT message."""
        stream = io.StringIO(newline="")
        csv.writer(stream, lineterminator="").writerow(self.values)

        return {
            BrokerConstants.TIMESTAMP_KEY: self.values[0],
            BrokerConstants.CORRELATION_ID_KEY: self.correlation_id,
            BrokerConstants.RAW_MESSAGE_KEY: stream.getvalue(),
        }


class DiskCache:
    """Write and read the CSV interface between the two workers."""

    def __init__(self, root: Path):
        self.root = root
        self.rejected = root / "rejected"

    def prepare(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.rejected.mkdir(parents=True, exist_ok=True)
        probe = self.root / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()

    def store(self, device_name: str, payload: bytes) -> tuple[Path, CachedMessage]:
        try:
            decoded = payload.decode("utf-8")
            values = next(csv.reader([decoded], strict=True))
        except (UnicodeDecodeError, csv.Error) as error:
            raise InvalidMessage(f"invalid CSV: {error}") from error
        if not values:
            raise InvalidMessage("the CSV message is empty")
        timestamp = normalize_timestamp(values[0])
        values[0] = timestamp.astimezone(dt.timezone.utc).isoformat()
        correlation_id = str(uuid.uuid4())
        cached = CachedMessage(correlation_id, device_name, tuple(values))
        path = self.root / f"{device_name}_{values[0]}_{correlation_id}.csv"
        temporary = path.with_suffix(".csv.tmp")
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerow((correlation_id, device_name, *values))
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        return path, cached

    def files(self) -> list[Path]:
        return sorted(self.root.glob("*.csv"), key=lambda path: (path.stat().st_ctime_ns, path.name))

    def load(self, path: Path) -> CachedMessage:
        try:
            with path.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.reader(stream, strict=True))
        except (UnicodeDecodeError, csv.Error) as error:
            raise InvalidMessage(f"invalid cached CSV: {error}") from error
        if len(rows) != 1 or len(rows[0]) < 3:
            raise InvalidMessage("the cache file must contain one CSV row with at least three fields")
        correlation_id, device_name, *values = rows[0]
        try:
            uuid.UUID(correlation_id)
        except ValueError as error:
            raise InvalidMessage("the cache file has an invalid correlation ID") from error
        if device_name not in ICT_EAGLEIO_DEVICE_NAMES:
            raise InvalidMessage(f"the cache file has unknown device {device_name!r}")
        try:
            timestamp = dateutil.parser.isoparse(values[0])
        except (TypeError, ValueError) as error:
            raise InvalidMessage("the cache file has an invalid timestamp") from error
        if timestamp.tzinfo is None:
            raise InvalidMessage("the cache timestamp has no timezone")
        return CachedMessage(correlation_id, device_name, tuple(values))

    def reject(self, path: Path, reason: str) -> None:
        target = self.rejected / path.name
        path.replace(target)
        target.with_suffix(".error.txt").write_text(reason + "\n", encoding="utf-8")


def translate(cached: CachedMessage, mapping: Mapping[str, Field]) -> dict[str, Any]:
    cache_fields = (cached.correlation_id, cached.device_name, *cached.values)
    try:
        return translate_cache_fields(cache_fields, mapping)
    except FieldMappingError as error:
        raise InvalidMessage(str(error)) from error


class ConfirmingPublisher:
    """Publish one persistent message and wait for broker confirmation."""

    def __init__(self, amqp_url: str):
        self.amqp_url = amqp_url
        self.connection: pika.BlockingConnection | None = None
        self.channel: Any = None

    def close(self) -> None:
        if self.connection is not None and self.connection.is_open:
            self.connection.close()
        self.connection = None
        self.channel = None

    def connect(self) -> None:
        self.close()
        self.connection = pika.BlockingConnection(pika.URLParameters(self.amqp_url))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(
            exchange=BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME,
            exchange_type=ExchangeType.fanout,
            durable=True,
        )
        self.channel.confirm_delivery()

    def process_data_events(self) -> None:
        """Service heartbeats and other events on an open publisher connection."""
        if self.connection is None or self.connection.is_closed:
            return
        try:
            self.connection.process_data_events(time_limit=0)
        except (OSError, pika.exceptions.AMQPError):
            self.close()
            raise

    def publish(self, message: Mapping[str, Any]) -> None:
        if self.channel is None or self.channel.is_closed:
            self.connect()
        properties = pika.BasicProperties(
            app_id="broker",
            content_type="application/json",
            delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE,
            correlation_id=str(message[BrokerConstants.CORRELATION_ID_KEY]),
        )
        try:
            accepted = self.channel.basic_publish(
                exchange=BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME,
                routing_key=ROUTING_KEY,
                body=json.dumps(message, ensure_ascii=False).encode("utf-8"),
                properties=properties,
            )
            if accepted is False:
                raise RuntimeError("RabbitMQ negatively acknowledged the message")
        except (pika.exceptions.AMQPError, RuntimeError):
            self.close()
            raise


class JsonMessageWriter:
    """Write translated messages atomically instead of publishing them."""

    def __init__(self, root: Path):
        self.root = root

    def prepare(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        probe = self.root / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()

    def write(self, cache_path: Path, message: Mapping[str, Any]) -> Path:
        output_path = self.root / cache_path.with_suffix(".json").name
        temporary = output_path.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(message, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(output_path)
        return output_path


def _dao() -> Any:
    """Import the DAO only when production processing needs it."""
    import api.client.DAO as dao

    return dao


class ICTMQTTReceiver:
    def __init__(self, config: Config, cache: DiskCache,
                 publisher: ConfirmingPublisher | None = None,
                 test_writer: JsonMessageWriter | None = None):
        self.config = config
        self.cache = cache
        self.publisher = publisher
        self.test_writer = test_writer
        self.stop_event = threading.Event()
        self.mqtt_client: mqtt.Client | None = None
        # Only the device worker reads or changes these two maps.
        self.legacy_devices: dict[str, Any] = {}
        self.devices: dict[str, Any] = {}
        self.database_ready = False

    def _initialize_database(self) -> None:
        dao = _dao()
        dao.add_physical_source(SOURCE)
        self.legacy_devices = {
            device.name: device for device in dao.get_physical_devices_from_source(LEGACY_SOURCE)
        }
        self.devices = {
            device.name: device for device in dao.get_physical_devices_from_source(SOURCE)
        }
        self.database_ready = True
        logging.info("Loaded %d EagleIO and %d ICT MQTT physical devices",
                     len(self.legacy_devices), len(self.devices))

    def _mqtt_worker(self) -> None:
        failures = 0
        while not self.stop_event.is_set():
            client: mqtt.Client | None = None
            try:
                logging.info("Connecting to ICT MQTT server %s:%d",
                             self.config.mqtt_server, self.config.mqtt_port)
                client = mqtt.Client(
                    mqtt.CallbackAPIVersion.VERSION2,
                    client_id=f"iota-ict-{uuid.uuid4().hex[:8]}",
                    manual_ack=True,
                )
                client.on_connect = self._on_connect
                client.on_disconnect = self._on_disconnect
                client.on_message = self._on_message
                self.mqtt_client = client
                client.connect(self.config.mqtt_server, self.config.mqtt_port,
                               self.config.mqtt_keepalive)
                failures = 0
                client.loop_forever(retry_first_connection=False)
                if not self.stop_event.is_set():
                    raise ConnectionError("the ICT MQTT network loop stopped")
            except (OSError, RuntimeError):
                if self.stop_event.is_set():
                    break
                failures += 1
                delay = retry_delay(failures)
                logging.exception("ICT MQTT connection failed; retry in %.1f seconds", delay)
                self.stop_event.wait(delay)
            finally:
                if client is not None:
                    try:
                        client.disconnect()
                    except OSError:
                        pass
        self.mqtt_client = None
        logging.info("The ICT MQTT worker stopped")

    def _on_connect(self, client: mqtt.Client, _userdata: Any, _flags: Any,
                    reason_code: Any, _properties: Any) -> None:
        if reason_code != 0:
            raise ConnectionError(f"the ICT MQTT server refused the connection: {reason_code}")
        result, _mid = client.subscribe(TOPIC_FILTER, qos=1)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"subscription to {TOPIC_FILTER} failed: {result}")
        logging.info("Connected and subscribed to ICT MQTT topic %s", TOPIC_FILTER)

    def _on_disconnect(self, _client: mqtt.Client, _userdata: Any, _disconnect_flags: Any,
                       reason_code: Any, _properties: Any) -> None:
        logging.info("Disconnected from the ICT MQTT server: %s", reason_code)

    def _on_message(self, client: mqtt.Client, _userdata: Any, message: mqtt.MQTTMessage) -> None:
        # A callback that started before shutdown can finish its current write.
        if self.stop_event.is_set():
            return
        try:
            device_name = device_name_from_topic(message.topic)
        except InvalidMessage:
            client.ack(message.mid, message.qos)
            return
        if device_name not in ICT_EAGLEIO_DEVICE_NAMES:
            client.ack(message.mid, message.qos)
            return
        try:
            _path, cached = self.cache.store(device_name, message.payload)
        except InvalidMessage as error:
            logging.info("Ignored malformed ICT MQTT message for %s: %s", device_name, error)
            client.ack(message.mid, message.qos)
            return
        except OSError:
            logging.exception("The ICT MQTT message for %s was not written", device_name)
            client.disconnect()
            return
        lu.cid_logger.info("Received ICT MQTT message for %s: %s", device_name,
                           message.payload.decode("utf-8", errors="replace"),
                           extra={BrokerConstants.CORRELATION_ID_KEY: cached.correlation_id})
        result = client.ack(message.mid, message.qos)
        if result != mqtt.MQTT_ERR_SUCCESS:
            logging.warning("MQTT acknowledgement failed for %s: %s", cached.correlation_id, result)

    def _device(self, cached: CachedMessage) -> Any:
        from pdmodels.Models import PhysicalDevice

        dao = _dao()
        if device := self.devices.get(cached.device_name):
            return device
        legacy = self.legacy_devices.get(cached.device_name)
        properties: dict[str, Any] = {
            BrokerConstants.CREATION_CORRELATION_ID_KEY: cached.correlation_id,
        }
        if legacy is not None:
            properties["replaces_ict_eagleio_uid"] = legacy.uid
        topic = f"ict/data/{cached.device_name}"
        device = dao.create_physical_device(PhysicalDevice(
            source_name=SOURCE,
            name=cached.device_name,
            location=legacy.location if legacy else None,
            last_seen=cached.timestamp,
            source_ids={"topic": topic},
            properties=properties,
        ))
        self.devices[cached.device_name] = device
        lu.cid_logger.info("Created ICT MQTT physical device %s", cached.device_name,
                           extra={BrokerConstants.CORRELATION_ID_KEY: cached.correlation_id})
        return device

    def _process_file(self, path: Path) -> None:
        cached = self.cache.load(path)
        mapping = field_mapping_for_device(cached.device_name)
        if mapping is None:
            self.cache.reject(path, "No field mapping.")
            return
        message = translate(cached, mapping)
        if self.config.test_mode:
            if self.test_writer is None:
                raise RuntimeError("the test-message writer is not configured")
            self.test_writer.write(path, message)
            path.unlink()
            return

        dao = _dao()
        if self.publisher is None:
            raise RuntimeError("the RabbitMQ publisher is not configured")
        device = self._device(cached)
        message[BrokerConstants.PHYSICAL_DEVICE_UID_KEY] = device.uid
        raw_message = cached.raw_message()
        dao.add_raw_json_message(
            SOURCE,
            cached.timestamp,
            cached.correlation_id,
            raw_message,
            device.uid,
        )
        self.publisher.publish(message)

        if device.last_seen is None or cached.timestamp > device.last_seen:
            device.last_seen = cached.timestamp
        device.properties[LAST_CORRELATION_ID] = cached.correlation_id
        device.properties[BrokerConstants.LAST_MSG] = raw_message
        self.devices[cached.device_name] = dao.update_physical_device(device)
        path.unlink()

    def _device_worker(self) -> None:
        if self.config.test_mode:
            self._test_device_worker()
            return

        dao = _dao()
        failures = 0
        while not self.stop_event.is_set() and not self.database_ready:
            try:
                logging.info("Connecting to the database for ICT MQTT processing")
                self._initialize_database()
                failures = 0
            except (OSError, dao.DAOException):
                failures += 1
                delay = retry_delay(failures)
                logging.exception("Database initialization failed; retry in %.1f seconds", delay)
                self.stop_event.wait(delay)

        while not self.stop_event.is_set():
            files = self.cache.files()
            if not files:
                try:
                    self.publisher.process_data_events()
                except (OSError, pika.exceptions.AMQPError):
                    logging.exception(
                        "RabbitMQ connection failed while waiting for a cache file; "
                        "the next publish will reconnect"
                    )
                self.stop_event.wait(10)
                continue
            path = files[0]
            try:
                self._process_file(path)
                failures = 0
            except InvalidMessage as error:
                logging.info("Rejected malformed ICT MQTT cache file %s: %s", path.name, error)
                try:
                    self.cache.reject(path, str(error))
                except OSError:
                    logging.exception("The cache file %s could not move to rejected", path.name)
                    self.stop_event.wait(1)
            except (OSError, dao.DAOException, pika.exceptions.AMQPError, RuntimeError):
                failures += 1
                self.publisher.close()
                self.database_ready = False
                delay = retry_delay(failures)
                logging.exception("Database or RabbitMQ processing failed; retry in %.1f seconds", delay)
                self.stop_event.wait(delay)
                while not self.stop_event.is_set() and not self.database_ready:
                    try:
                        self._initialize_database()
                    except (OSError, dao.DAOException):
                        logging.exception("Database reconnection failed; retry in 60 seconds")
                        self.stop_event.wait(60 + random.uniform(0, 10))
        self.publisher.close()
        dao.stop()
        logging.info("The ICT physical-device worker stopped")

    def _test_device_worker(self) -> None:
        if self.test_writer is None:
            raise RuntimeError("the test-message writer is not configured")
        self.test_writer.prepare()
        logging.info("ICT MQTT test mode writes messages to %s", self.test_writer.root)
        while not self.stop_event.is_set():
            processed = False
            for path in self.cache.files():
                if self.stop_event.is_set():
                    break
                try:
                    self._process_file(path)
                    processed = True
                except InvalidMessage as error:
                    logging.info("Rejected malformed ICT MQTT cache file %s: %s", path.name, error)
                    try:
                        self.cache.reject(path, str(error))
                    except OSError:
                        logging.exception("The cache file %s could not move to rejected", path.name)
                except OSError:
                    logging.exception("Test-mode processing failed for %s", path.name)
                    self.stop_event.wait(1)
                    break
            if not processed:
                self.stop_event.wait(1)
        logging.info("The ICT test-message worker stopped")

    def run(self) -> None:
        self.cache.prepare()
        workers = (
            threading.Thread(target=self._mqtt_worker, name="ict-mqtt"),
            threading.Thread(target=self._device_worker, name="ict-physical-device"),
        )
        for worker in workers:
            worker.start()
        unexpected_failure = False
        try:
            while not self.stop_event.wait(1):
                failed = next((worker for worker in workers if not worker.is_alive()), None)
                if failed is not None:
                    logging.error("Worker %s stopped unexpectedly", failed.name)
                    unexpected_failure = True
                    self.stop_event.set()
                    break
        finally:
            self.stop()
            for worker in workers:
                worker.join()
        if unexpected_failure:
            raise RuntimeError("an ICT MQTT worker stopped unexpectedly")

    def stop(self) -> None:
        if not self.stop_event.is_set():
            logging.info("Stopping the ICT MQTT receiver")
        self.stop_event.set()
        if self.mqtt_client is not None:
            try:
                self.mqtt_client.disconnect()
            except OSError:
                logging.exception("The ICT MQTT client did not disconnect cleanly")


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format=BrokerConstants.LOGGER_FORMAT)
    logging.info('===============================================================')
    logging.info('               STARTING ICT MQTT RECEIVER')
    logging.info('===============================================================')

    validate_field_mappings()
    config = Config.from_environment()
    if config.test_mode:
        receiver = ICTMQTTReceiver(
            config,
            DiskCache(config.cache_dir),
            test_writer=JsonMessageWriter(config.test_message_dir),
        )
    else:
        receiver = ICTMQTTReceiver(
            config,
            DiskCache(config.cache_dir),
            publisher=ConfirmingPublisher(config.amqp_url),
        )

    def stop(_signum: int, _frame: Any) -> None:
        receiver.stop()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    receiver.run()


if __name__ == "__main__":
    main()
