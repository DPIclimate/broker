"""Poll TagoIO devices and publish water-quality readings to IoTa.

Every successful API response is written to ``TAGO_SPOOL_DIR`` before it is
processed.  A spool file is removed only after every record in it has been
confirmed by RabbitMQ (or deliberately quarantined as invalid).
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import logging
import os
import random
import re
import signal
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import dateutil.parser
import pika
import requests
from pika.exchange_type import ExchangeType

import BrokerConstants
import api.client.DAO as dao
from pdmodels.Models import PhysicalDevice
import util.LoggingUtil as lu

UUID_NAMESPACE = uuid.UUID("79482d73-724b-4d9d-9957-cf7bdcd077d1")

class ConfigurationError(RuntimeError):
    pass


class TagoAPIError(RuntimeError):
    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class InvalidRecord(ValueError):
    pass


@dataclass(frozen=True)
class DeviceColumns:
    """The device-specific CSV layout returned by Tago parameters."""

    names: tuple[str, ...]
    pump_index: int

    @classmethod
    def from_params(cls, params: Sequence[dict[str, Any]]) -> "DeviceColumns":
        values = {
            str(param.get("key")): param.get("value")
            for param in params
            if isinstance(param, dict) and param.get("key") is not None
        }
        header = values.get("header")
        if not isinstance(header, str) or not header.strip():
            raise TagoAPIError("Tago device parameters did not contain a header")
        try:
            names = tuple(name.strip() for name in next(csv.reader([header])))
        except csv.Error as error:
            raise TagoAPIError(f"Invalid Tago header parameter: {error}") from error
        if not names or any(not name for name in names):
            raise TagoAPIError("Tago header parameter contained an empty column name")

        index = values.get("index")
        try:
            pump_index = int(index) - 1
        except (TypeError, ValueError) as error:
            raise TagoAPIError("Tago device parameters did not contain a valid index") from error
        if pump_index < 1:
            raise TagoAPIError("Tago index must identify a data column after the timestamp")
        return cls(names=names, pump_index=pump_index)


@dataclass(frozen=True)
class Config:
    tokens: tuple[str, ...]
    spool_dir: Path
    api_base_url: str = "https://api.us-e1.tago.io"
    poll_interval: int = 3600
    initial_lookback: int = 86400
    page_size: int = 1000
    request_timeout: int = 30
    max_backoff: int = 3600
    data_timezone: str = "Australia/Sydney"

    @classmethod
    def from_environment(cls) -> "Config":
        tokens = tuple(token.strip() for token in os.getenv("TAGO_DEVICE_TOKENS", "").split(",") if token.strip())
        if not tokens:
            raise ConfigurationError("TAGO_DEVICE_TOKENS must contain at least one device token")
        data_timezone = os.getenv("TAGO_DATA_TIMEZONE", "Australia/Sydney")
        try:
            ZoneInfo(data_timezone)
        except ZoneInfoNotFoundError as error:
            raise ConfigurationError(f"TAGO_DATA_TIMEZONE is not valid: {data_timezone}") from error
        return cls(
            tokens=tokens,
            spool_dir=Path(os.getenv("TAGO_SPOOL_DIR", "/var/spool/tago")),
            api_base_url=os.getenv("TAGO_API_BASE_URL", "https://api.eu-w1.tago.io").rstrip("/"),
            poll_interval=_positive_int("TAGO_POLL_INTERVAL", 3600),
            initial_lookback=_positive_int("TAGO_INITIAL_LOOKBACK", 86400),
            page_size=_positive_int("TAGO_PAGE_SIZE", 1000),
            request_timeout=_positive_int("TAGO_REQUEST_TIMEOUT", 30),
            max_backoff=_positive_int("TAGO_MAX_BACKOFF", 3600),
            data_timezone=data_timezone,
        )


def _positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ConfigurationError(f"{name} must be a positive integer")
    return value


def _retry_after(response: requests.Response) -> float | None:
    header = response.headers.get("Retry-After")
    if header:
        try:
            return max(1.0, float(header))
        except ValueError:
            pass
    match = re.search(r"Retry-After:\s*(\d+)", response.text, re.IGNORECASE)
    return float(match.group(1)) if match else None


class TagoClient:
    def __init__(self, base_url: str, timeout: int, session: requests.Session | None = None):
        self.base_url = base_url
        self.timeout = timeout
        self.session = session or requests.Session()

    def get(self, token: str, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self.session.get(
                f"{self.base_url}{path}", params=params,
                headers={"Accept": "application/json", "Device-Token": token},
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise TagoAPIError(f"Tago request failed: {error}") from error
        if response.status_code == 429:
            raise TagoAPIError("Tago rate limit reached", _retry_after(response))
        try:
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as error:
            raise TagoAPIError(f"Invalid Tago response ({response.status_code}): {response.text[:300]}") from error
        if not isinstance(body, dict) or body.get("status") is not True:
            raise TagoAPIError(f"Tago returned an unsuccessful response: {body}")
        return body

    def device_info(self, token: str) -> dict[str, Any]:
        result = self.get(token, "/info").get("result")
        if not isinstance(result, dict):
            raise TagoAPIError("Tago device information was not an object")
        return result

    def device_params(self, token: str) -> DeviceColumns:
        result = self.get(token, "/device/params").get("result")
        if not isinstance(result, list):
            raise TagoAPIError("Tago device parameters did not contain a result list")
        return DeviceColumns.from_params(result)

    def data_pages(self, token: str, start: dt.datetime, end: dt.datetime,
                   page_size: int) -> Iterator[dict[str, Any]]:
        skip = 0
        while True:
            body = self.get(token, "/data", {
                "details": "true", "ordination": "ascending", "variables": "export",
                "start_date": _iso_z(start), "end_date": _iso_z(end),
                "qty": page_size, "skip": skip,
            })
            result = body.get("result")
            if not isinstance(result, list):
                raise TagoAPIError("Tago data response did not contain a result list")
            yield body
            if len(result) < page_size:
                break
            skip += len(result)


class Spool:
    def __init__(self, root: Path):
        self.pending = root / "pending"
        self.quarantine = root / "quarantine"

    def prepare(self) -> None:
        self.pending.mkdir(parents=True, exist_ok=True)
        self.quarantine.mkdir(parents=True, exist_ok=True)
        probe = self.pending / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()

    def store(self, device_id: str, response: dict[str, Any]) -> Path:
        digest = hashlib.sha256(json.dumps(response, sort_keys=True).encode()).hexdigest()[:16]
        path = self.pending / f"{_safe_name(device_id)}-{digest}.json"
        if not path.exists():
            _atomic_json(path, {"device_id": device_id, "response": response, "completed_ids": []})
        return path

    def files(self) -> list[Path]:
        return sorted(self.pending.glob("*.json"))

    def load(self, path: Path) -> dict[str, Any]:
        with path.open(encoding="utf-8") as stream:
            return json.load(stream)

    def mark_completed(self, path: Path, document: dict[str, Any], record_id: str) -> None:
        document.setdefault("completed_ids", []).append(record_id)
        _atomic_json(path, document)

    def quarantine_record(self, path: Path, record: Any, reason: str) -> None:
        name = f"{path.stem}-{uuid.uuid4().hex[:8]}.json"
        _atomic_json(self.quarantine / name, {"reason": reason, "record": record})


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value)


def _iso_z(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_record(record: dict[str, Any], columns: DeviceColumns,
                 data_timezone: str = "Australia/Sydney") -> tuple[dt.datetime, list[dict[str, Any]]]:
    if record.get("variable") != "export":
        raise InvalidRecord(f"unsupported variable {record.get('variable')!r}")
    value = record.get("value")
    if not isinstance(value, str):
        raise InvalidRecord("value is not a CSV string")
    try:
        values = next(csv.reader([value]))
    except csv.Error as error:
        raise InvalidRecord(f"invalid CSV: {error}") from error
    if len(values) < len(columns.names):
        raise InvalidRecord(
            f"device header defines {len(columns.names)} CSV fields, received {len(values)}"
        )
    if columns.pump_index >= len(values):
        raise InvalidRecord(
            f"pump index {columns.pump_index + 1} is outside the {len(values)} CSV fields"
        )
    try:
        timestamp = dateutil.parser.parse(values[0])
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=ZoneInfo(data_timezone))
        timestamp = timestamp.astimezone(dt.timezone.utc)
    except (TypeError, ValueError, OverflowError, ZoneInfoNotFoundError) as error:
        raise InvalidRecord("missing or invalid CSV timestamp") from error

    readings = []
    unnamed_count = 0
    for index, raw_value in enumerate(values[1:], start=1):
        if index < len(columns.names):
            name = columns.names[index]
        else:
            unnamed_count += 1
            name = f"unknown_{unnamed_count}"
        if index == columns.pump_index:
            name = "pump_number"
        try:
            value_number: int | float = int(raw_value) if re.fullmatch(r"[-+]?\d+", raw_value) else float(raw_value)
        except ValueError as error:
            raise InvalidRecord(f"{name} is not numeric: {raw_value!r}") from error
        readings.append({"name": name, "value": value_number})
    return timestamp, readings


class ConfirmingPublisher:
    def __init__(self, amqp_url: str):
        self.amqp_url = amqp_url
        self.connection: pika.BlockingConnection | None = None
        self.channel = None

    def close(self) -> None:
        if self.connection and self.connection.is_open:
            self.connection.close()
        self.connection = None
        self.channel = None

    def _connect(self) -> None:
        self.close()
        self.connection = pika.BlockingConnection(pika.URLParameters(self.amqp_url))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange=BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME,
                                      exchange_type=ExchangeType.fanout, durable=True)
        self.channel.confirm_delivery()

    def publish(self, message: dict[str, Any]) -> None:
        if self.channel is None or self.channel.is_closed:
            self._connect()
        properties = pika.BasicProperties(app_id="broker", content_type="application/json",
                                          delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE,
                                          correlation_id=message[BrokerConstants.CORRELATION_ID_KEY])
        try:
            confirmed = self.channel.basic_publish(
                exchange=BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME,
                routing_key="physical_timeseries",
                body=json.dumps(message, ensure_ascii=False).encode(),
                properties=properties,
            )
            if confirmed is False:
                raise RuntimeError("RabbitMQ negatively acknowledged the message")
        except (pika.exceptions.AMQPError, RuntimeError):
            self.close()
            raise


def _amqp_url() -> str:
    required = ("RABBITMQ_DEFAULT_USER", "RABBITMQ_DEFAULT_PASS", "RABBITMQ_HOST", "RABBITMQ_PORT")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise ConfigurationError(f"Missing RabbitMQ settings: {', '.join(missing)}")
    user = quote(os.environ[required[0]], safe="")
    password = quote(os.environ[required[1]], safe="")
    host = os.environ[required[2]]
    port = int(os.environ[required[3]])
    return f"amqp://{user}:{password}@{host}:{port}/%2F"


class TagoPoller:
    def __init__(self, config: Config, client: TagoClient, spool: Spool,
                 publisher: ConfirmingPublisher, sleep: Callable[[float], None] = time.sleep):
        self.config = config
        self.client = client
        self.spool = spool
        self.publisher = publisher
        self.sleep = sleep
        self.devices: dict[str, PhysicalDevice] = {}
        self.token_device_ids: dict[str, str] = {}
        self.device_columns: dict[str, DeviceColumns] = {}

    def initialise(self) -> None:
        self.spool.prepare()
        dao.add_physical_source(BrokerConstants.TAGO)
        for token in self.config.tokens:
            info = self.client.device_info(token)
            device_id_value = info.get("device_id")
            if not device_id_value:
                raise TagoAPIError("Tago device information did not contain device_id")
            device_id = str(device_id_value)
            self.token_device_ids[token] = device_id
            self.device_columns[device_id] = self.client.device_params(token)
            source_ids = {"device_id": device_id}
            devices = dao.get_pyhsical_devices_using_source_ids(BrokerConstants.TAGO, source_ids)
            if devices:
                device = devices[0]
            else:
                tags = info.get("tags") if isinstance(info.get("tags"), list) else []
                tagged_name = next(
                    (tag.get("value") for tag in tags
                     if isinstance(tag, dict) and tag.get("key") == "dev_name"),
                    None,
                )
                device_name = str(tagged_name or info.get("name") or device_id).strip() or device_id
                correlation_id = str(uuid.uuid5(UUID_NAMESPACE, f"device:{device_id}"))

                device = dao.create_physical_device(PhysicalDevice(
                    source_name=BrokerConstants.TAGO, name=device_name, location=None,
                    source_ids=source_ids,
                    properties={
                        BrokerConstants.TAGO: info,
                        BrokerConstants.CREATION_CORRELATION_ID_KEY: correlation_id,
                    },
                ))
            self.devices[device_id] = device
        # Pending responses require the device-specific header and pump index.
        self._drain_spool()

    def poll_once(self) -> None:
        self._drain_spool()
        end = dt.datetime.now(dt.timezone.utc)
        for token in self.config.tokens:
            device_id = self.token_device_ids[token]
            device = self.devices.get(device_id)
            if device is None:
                raise RuntimeError(f"Tago device {device_id} was not initialised")
            start = device.last_seen or end - dt.timedelta(seconds=self.config.initial_lookback)
            for response in self.client.data_pages(token, start, end, self.config.page_size):
                self.spool.store(device_id, response)
            self._drain_spool()

    def _drain_spool(self) -> None:
        for path in self.spool.files():
            document = self.spool.load(path)
            device_id = str(document.get("device_id", ""))
            device = self.devices.get(device_id)
            if device is None:
                devices = dao.get_pyhsical_devices_using_source_ids(BrokerConstants.TAGO, {"device_id": device_id})
                if not devices:
                    logging.warning("Leaving %s pending: physical device %s does not exist", path, device_id)
                    continue
                device = devices[0]
                self.devices[device_id] = device
            columns = self.device_columns.get(device_id)
            if columns is None:
                logging.warning("Leaving %s pending: no column definition for device %s", path, device_id)
                continue
            records = document.get("response", {}).get("result")
            if not isinstance(records, list):
                self.spool.quarantine_record(path, document, "response result is not a list")
                path.unlink()
                continue
            completed = set(document.get("completed_ids", []))
            for record in records:
                record_id = str(record.get("id", "")) if isinstance(record, dict) else ""
                if not record_id:
                    self.spool.quarantine_record(path, record, "record has no id")
                    record_id = f"invalid-{uuid.uuid4()}"
                    self.spool.mark_completed(path, document, record_id)
                    continue
                if record_id in completed:
                    continue
                correlation_id = str(uuid.uuid5(UUID_NAMESPACE, f"{device_id}:{record_id}"))
                msg_with_cid = {
                    BrokerConstants.CORRELATION_ID_KEY: correlation_id,
                    BrokerConstants.RAW_MESSAGE_KEY: record,
                }
                try:
                    timestamp, readings = parse_record(record, columns, self.config.data_timezone)
                except InvalidRecord as error:
                    lu.cid_logger.error("Quarantining Tago record %s: %s", record_id, error,
                                        extra=msg_with_cid)
                    self.spool.quarantine_record(path, record, str(error))
                    self.spool.mark_completed(path, document, record_id)
                    continue
                # A crash can occur after the database checkpoint but before the
                # spool update. Do not republish that already-checkpointed record.
                if device.last_seen and (
                    timestamp < device.last_seen
                    or (timestamp == device.last_seen
                        and device.properties.get("last_tago_record_id") == record_id)
                ):
                    lu.cid_logger.info("Skipping already checkpointed Tago record %s",
                                       record_id, extra=msg_with_cid)
                    self.spool.mark_completed(path, document, record_id)
                    continue
                message = {
                    BrokerConstants.CORRELATION_ID_KEY: correlation_id,
                    BrokerConstants.PHYSICAL_DEVICE_UID_KEY: device.uid,
                    BrokerConstants.TIMESTAMP_KEY: _iso_z(timestamp),
                    BrokerConstants.TIMESERIES_KEY: readings,
                    "source_ids": {"device_id": device_id, "tago_record_id": record_id},
                }
                lu.cid_logger.info("Accepted Tago record %s from device %s",
                                   record_id, device_id, extra=message)
                try:
                    dao.add_raw_json_message(BrokerConstants.TAGO, timestamp, correlation_id, record, device.uid)
                    lu.cid_logger.info("Publishing physical timeseries message", extra=message)
                    self.publisher.publish(message)  # returns only after broker confirmation
                    lu.cid_logger.info("RabbitMQ acknowledged physical timeseries message", extra=message)
                    device.last_seen = max(filter(None, (device.last_seen, timestamp)))
                    device.properties[BrokerConstants.LAST_MSG] = json.dumps(message, ensure_ascii=False)
                    device.properties["last_tago_record_id"] = record_id
                    device = dao.update_physical_device(device)
                    self.devices[device_id] = device
                    self.spool.mark_completed(path, document, record_id)
                    lu.cid_logger.info("Checkpointed Tago record and updated spool", extra=message)
                except (OSError, dao.DAOException, pika.exceptions.AMQPError, RuntimeError):
                    lu.cid_logger.exception("Failed while processing Tago record", extra=message)
                    raise
            if len(set(document.get("completed_ids", []))) >= len(records):
                path.unlink()

    def run(self) -> None:
        failures = 0
        while True:
            started = time.monotonic()
            try:
                self.poll_once()
                failures = 0
                delay = max(0.0, self.config.poll_interval - (time.monotonic() - started))
            except TagoAPIError as error:
                failures += 1
                delay = error.retry_after or _backoff(failures, self.config.max_backoff)
                logging.error("%s; next attempt in %.0f seconds", error, delay)
            except (OSError, json.JSONDecodeError, dao.DAOException, pika.exceptions.AMQPError, RuntimeError) as error:
                failures += 1
                delay = _backoff(failures, self.config.max_backoff)
                logging.exception("Poll cycle failed; next attempt in %.0f seconds", delay)
            self.sleep(delay)


def _backoff(failures: int, maximum: int) -> float:
    base = min(maximum, 5 * (2 ** min(failures - 1, 10)))
    return min(maximum, base + random.uniform(0, base * 0.2))


def main() -> None:
    config = Config.from_environment()
    poller = TagoPoller(config, TagoClient(config.api_base_url, config.request_timeout),
                        Spool(config.spool_dir), ConfirmingPublisher(_amqp_url()))

    def stop(_signum: int, _frame: Any) -> None:
        logging.info("Stopping Tago poller")
        poller.publisher.close()
        dao.stop()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logging.info("Starting Tago poller for %d device token(s)", len(config.tokens))
    failures = 0
    while True:
        try:
            poller.initialise()
            break
        except (TagoAPIError, OSError, dao.DAOException, pika.exceptions.AMQPError) as error:
            failures += 1
            delay = error.retry_after if isinstance(error, TagoAPIError) else None
            delay = delay or _backoff(failures, config.max_backoff)
            logging.exception("Initialisation failed; retrying in %.0f seconds", delay)
            time.sleep(delay)
    poller.run()


if __name__ == "__main__":
    main()
