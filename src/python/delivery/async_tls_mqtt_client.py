#!/usr/bin/env python3
"""TLS-enabled MQTT monitor and async JSON publisher using paho-mqtt."""

import argparse
import asyncio
import datetime
import json
import logging
import math
import signal
import ssl
from dataclasses import dataclass
from functools import cache
from typing import Any, Dict, List, Optional, Tuple

try:
    import paho.mqtt.client as mqtt
except ModuleNotFoundError as exc:
    raise SystemExit("Missing dependency: paho-mqtt. Install with: pip install paho-mqtt") from exc

try:
    import psycopg2
except ModuleNotFoundError as exc:
    raise SystemExit("Missing dependency: psycopg2. Install with: pip install psycopg2") from exc


@dataclass(frozen=True)
class MonitoredMessage:
    topic: str
    payload: bytes
    qos: int
    retain: bool


TB_GATEWAY_TELEMETRY_TOPIC = "v1/gateway/telemetry"
logging.basicConfig(level=logging.INFO, format="%(asctime)s|%(levelname)s|%(message)s")
logger = logging.getLogger(__name__)


class AsyncTlsMqttClient:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        topics: List[Tuple[str, int]],
        client_id: str = "",
        username: Optional[str] = None,
        password: Optional[str] = None,
        keepalive: int = 60,
        ca_cert: Optional[str] = None,
        cert_file: Optional[str] = None,
        key_file: Optional[str] = None,
        insecure_tls: bool = False,
        connect_timeout: float = 10.0,
        publish_timeout: float = 10.0,
    ):
        """Initialise a TLS MQTT client wrapper around paho.

        Args:
            host: MQTT broker hostname or IP.
            port: MQTT broker TLS port.
            topics: List of (topic_filter, qos) pairs to subscribe to on connect.
            client_id: MQTT client identifier.
            username: Optional username used for broker authentication.
            password: Optional password used for broker authentication.
            keepalive: MQTT keepalive interval in seconds.
            ca_cert: Optional path to a CA certificate PEM file.
            cert_file: Optional path to a client certificate PEM file.
            key_file: Optional path to a client private key PEM file.
            insecure_tls: When true, disables TLS hostname verification.
            connect_timeout: Maximum time to wait for MQTT connect acknowledgement.
            publish_timeout: Maximum time to wait for publish acknowledgement.

        Returns:
            None.
        """
        self.host = host
        self.port = port
        self.keepalive = keepalive
        self.topics = topics
        self.connect_timeout = connect_timeout
        self.publish_timeout = publish_timeout

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv311,
            reconnect_on_failure=False,
        )
        if username:
            self._client.username_pw_set(username, password)

        self._client.tls_set(
            ca_certs=ca_cert,
            certfile=cert_file,
            keyfile=key_file,
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )
        self._client.tls_insecure_set(insecure_tls)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.on_publish = self._on_publish

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._connect_event: Optional[asyncio.Event] = None
        self._disconnect_event: Optional[asyncio.Event] = None
        self._message_queue: Optional[asyncio.Queue[MonitoredMessage]] = None
        self._pending_publishes: Dict[int, asyncio.Future[None]] = {}
        self._connect_error: Optional[str] = None
        self._disconnect_reason: Optional[Any] = None
        self._closing = False

    @staticmethod
    def _connect_reason_is_success(reason_code: Any) -> bool:
        """Handle paho callback API reason code values across versions."""
        if hasattr(reason_code, "is_failure"):
            return not bool(reason_code.is_failure)
        try:
            return int(reason_code) == 0
        except (TypeError, ValueError):
            return str(reason_code).lower() in {"success", "0"}

    async def connect(self) -> None:
        """Connect to the MQTT broker and subscribe to configured topics.

        Args:
            None.

        Returns:
            None.

        Raises:
            TimeoutError: If connect acknowledgement is not received in time.
            ConnectionError: If broker connection or subscription setup fails.
        """
        self._loop = asyncio.get_running_loop()
        self._connect_event = asyncio.Event()
        self._disconnect_event = asyncio.Event()
        self._message_queue = asyncio.Queue()
        self._connect_error = None
        self._disconnect_reason = None
        self._closing = False

        self._client.connect_async(self.host, self.port, self.keepalive)
        self._client.loop_start()

        try:
            await asyncio.wait_for(self._connect_event.wait(), timeout=self.connect_timeout)
        except asyncio.TimeoutError as exc:
            self._client.loop_stop()
            raise TimeoutError("Timed out waiting for MQTT connection.") from exc

        if self._connect_error:
            await self.close()
            raise ConnectionError(self._connect_error)

    async def close(self) -> None:
        """Disconnect from MQTT and stop the paho network loop thread.

        Args:
            None.

        Returns:
            None.
        """
        self._closing = True
        if self._client.is_connected():
            self._client.disconnect()
            if self._disconnect_event is not None:
                try:
                    await asyncio.wait_for(self._disconnect_event.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass
        self._client.loop_stop()

    async def wait_for_disconnect(self) -> None:
        """Wait for disconnect event and fail on unexpected disconnect.

        Args:
            None.

        Returns:
            None.

        Raises:
            RuntimeError: If called before connect initialises state.
            ConnectionError: If MQTT disconnects unexpectedly.
        """
        if self._disconnect_event is None:
            raise RuntimeError("Client is not connected.")

        await self._disconnect_event.wait()
        if not self._closing:
            raise ConnectionError(f"MQTT connection lost: {self._disconnect_reason}")

    async def next_message(self) -> MonitoredMessage:
        """Return the next received MQTT message from the async queue.

        Args:
            None.

        Returns:
            The next monitored message.

        Raises:
            RuntimeError: If the client has not been connected.
        """
        if self._message_queue is None:
            raise RuntimeError("Client is not connected.")
        return await self._message_queue.get()

    async def send_json(self, topic: str, payload: Dict[str, Any]) -> None:
        """Publish a JSON payload to an MQTT topic asynchronously.

        Args:
            topic: Destination MQTT topic.
            payload: JSON-serialisable dict payload.

        Returns:
            None.

        Raises:
            RuntimeError: If client is disconnected or publish call fails.
            TypeError: If payload is not a dict.
            asyncio.TimeoutError: If publish acknowledgement times out.
        """
        if self._loop is None or self._connect_event is None or not self._connect_event.is_set():
            raise RuntimeError("Client is not connected.")
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dict.")

        data = json.dumps(payload, separators=(",", ":"))
        publish_info = self._client.publish(topic, data, qos=1, retain=False)
        if publish_info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"publish failed with code {publish_info.rc}")

        future = self._loop.create_future()
        self._pending_publishes[publish_info.mid] = future
        try:
            await asyncio.wait_for(future, timeout=self.publish_timeout)
        finally:
            self._pending_publishes.pop(publish_info.mid, None)

    # Paho callback handlers are invoked on paho's network thread.
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        """Handle MQTT connect acknowledgement and topic subscriptions.

        Args:
            client: Paho MQTT client instance.
            userdata: Opaque paho user data (unused).
            flags: MQTT connection flags (unused).
            reason_code: Connect result code or object.
            properties: MQTT v5 properties (unused).

        Returns:
            None.
        """
        if self._connect_reason_is_success(reason_code):
            for topic, qos in self.topics:
                result, _ = client.subscribe(topic, qos=qos)
                if result != mqtt.MQTT_ERR_SUCCESS:
                    self._connect_error = f"Failed to subscribe to topic '{topic}'."
                    break
        else:
            self._connect_error = f"MQTT connect failed with reason code {reason_code}."

        if self._loop and self._connect_event:
            self._loop.call_soon_threadsafe(self._connect_event.set)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        """Handle MQTT disconnection callback.

        Args:
            client: Paho MQTT client instance.
            userdata: Opaque paho user data (unused).
            disconnect_flags: MQTT disconnect flags (unused).
            reason_code: Disconnect reason code.
            properties: MQTT v5 properties (unused).

        Returns:
            None.
        """
        self._disconnect_reason = reason_code
        if self._loop and self._disconnect_event:
            self._loop.call_soon_threadsafe(self._disconnect_event.set)

    def _on_message(self, client, userdata, msg):
        """Handle inbound MQTT messages and enqueue them for async consumers.

        Args:
            client: Paho MQTT client instance.
            userdata: Opaque paho user data (unused).
            msg: Paho MQTTMessage object.

        Returns:
            None.
        """
        if self._loop and self._message_queue:
            monitored = MonitoredMessage(
                topic=msg.topic,
                payload=msg.payload,
                qos=msg.qos,
                retain=msg.retain,
            )
            self._loop.call_soon_threadsafe(self._message_queue.put_nowait, monitored)

    def _on_publish(self, client, userdata, mid, reason_code=None, properties=None):
        """Handle publish acknowledgement and resolve pending publish futures.

        Args:
            client: Paho MQTT client instance.
            userdata: Opaque paho user data (unused).
            mid: MQTT message id for the published packet.
            reason_code: MQTT publish result code (optional).
            properties: MQTT v5 properties (optional).

        Returns:
            None.
        """
        future = self._pending_publishes.get(mid)
        if future and self._loop and not future.done():
            self._loop.call_soon_threadsafe(future.set_result, None)


@dataclass(frozen=True)
class PhysicalTimeseriesRow:
    uid: int
    physical_uid: int
    logical_uid: int
    ts: datetime.datetime
    received_at: datetime.datetime
    json_msg: Any


class PhysicalTimeseriesMonitor:
    def __init__(self, poll_interval_seconds: float = 300.0):
        """Initialise database monitor state for physical_timeseries polling.

        Args:
            poll_interval_seconds: Polling interval in seconds.

        Returns:
            None.
        """
        self.poll_interval_seconds = poll_interval_seconds
        self._last_received_at: Optional[datetime.datetime] = None
        self._last_uid: int = 0

    async def initialise_checkpoint(self) -> None:
        """Initialise row checkpoint to the most recent eligible database row.

        Args:
            None.

        Returns:
            None.
        """
        last = await asyncio.to_thread(self._fetch_latest_row_sync)
        if last is None:
            self._last_received_at = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
            self._last_uid = 0
            return
        self._last_received_at, self._last_uid = last

    async def poll_new_rows(self) -> List[PhysicalTimeseriesRow]:
        """Fetch rows newer than the current (received_at, uid) checkpoint.

        Args:
            None.

        Returns:
            A list of newly observed physical_timeseries rows in ascending order.

        Raises:
            RuntimeError: If monitor checkpoint has not been initialised.
        """
        if self._last_received_at is None:
            raise RuntimeError("Database monitor not initialised.")

        rows = await asyncio.to_thread(self._fetch_new_rows_sync, self._last_received_at, self._last_uid)
        if rows:
            newest = rows[-1]
            self._last_received_at = newest.received_at
            self._last_uid = newest.uid
        return rows

    async def fetch_rows_in_date_range(
        self,
        from_date: datetime.date,
        to_date: datetime.date,
    ) -> List[PhysicalTimeseriesRow]:
        """Fetch mapped physical_timeseries rows between two local calendar dates.

        Args:
            from_date: Inclusive start date in local timezone.
            to_date: Inclusive end date in local timezone.

        Returns:
            Rows ordered by (ts, uid).
        """
        local_tz = datetime.datetime.now().astimezone().tzinfo
        if local_tz is None:
            local_tz = datetime.timezone.utc

        from_start = datetime.datetime.combine(from_date, datetime.time.min, tzinfo=local_tz)
        to_end_exclusive = datetime.datetime.combine(
            to_date + datetime.timedelta(days=1),
            datetime.time.min,
            tzinfo=local_tz,
        )

        return await asyncio.to_thread(self._fetch_rows_in_date_range_sync, from_start, to_end_exclusive)

    @staticmethod
    def _fetch_latest_row_sync() -> Optional[Tuple[datetime.datetime, int]]:
        """Read latest eligible checkpoint row from Postgres.

        Args:
            None.

        Returns:
            Tuple of (received_at, uid) for the newest row, or None if no rows.
        """
        query = """
            SELECT received_at, uid
            FROM physical_timeseries
            WHERE logical_uid IS NOT NULL
              AND received_at < now()
            ORDER BY received_at DESC, uid DESC
            LIMIT 1
        """
        with psycopg2.connect() as conn, conn.cursor() as curs:
            curs.execute(query)
            row = curs.fetchone()
            if row is None:
                return None
            return row[0], row[1]

    @staticmethod
    def _fetch_new_rows_sync(
        last_received_at: datetime.datetime,
        last_uid: int,
    ) -> List[PhysicalTimeseriesRow]:
        """Read rows newer than checkpoint in a deterministic order.

        Args:
            last_received_at: Last processed row's received_at timestamp.
            last_uid: Last processed row's UID used as tie-breaker.

        Returns:
            List of new physical_timeseries rows ordered by (received_at, uid).
        """
        query = """
            SELECT uid, physical_uid, logical_uid, ts, received_at, json_msg
            FROM physical_timeseries
            WHERE logical_uid IS NOT NULL
              AND received_at < now()
              AND (received_at > %s OR (received_at = %s AND uid > %s))
            ORDER BY received_at ASC, uid ASC
        """
        with psycopg2.connect() as conn, conn.cursor() as curs:
            curs.execute(query, (last_received_at, last_received_at, last_uid))
            return [
                PhysicalTimeseriesRow(
                    uid=row[0],
                    physical_uid=row[1],
                    logical_uid=row[2],
                    ts=row[3],
                    received_at=row[4],
                    json_msg=row[5],
                )
                for row in curs.fetchall()
            ]

    @staticmethod
    def _fetch_rows_in_date_range_sync(
        from_start: datetime.datetime,
        to_end_exclusive: datetime.datetime,
    ) -> List[PhysicalTimeseriesRow]:
        """Read rows in a timestamp date window.

        Args:
            from_start: Inclusive lower timestamp bound.
            to_end_exclusive: Exclusive upper timestamp bound.

        Returns:
            List of physical_timeseries rows ordered by (ts, uid).
        """
        query = """
            SELECT uid, physical_uid, logical_uid, ts, received_at, json_msg
            FROM physical_timeseries
            WHERE logical_uid IS NOT NULL
              AND ts >= %s
              AND ts < %s
            ORDER BY ts ASC, uid ASC
        """
        with psycopg2.connect() as conn, conn.cursor() as curs:
            curs.execute(query, (from_start, to_end_exclusive))
            return [
                PhysicalTimeseriesRow(
                    uid=row[0],
                    physical_uid=row[1],
                    logical_uid=row[2],
                    ts=row[3],
                    received_at=row[4],
                    json_msg=row[5],
                )
                for row in curs.fetchall()
            ]

    @staticmethod
    @cache
    def fetch_logical_device_name(logical_uid: int) -> Optional[str]:
        """Read logical device name for a UID from Postgres with memoized cache.

        Args:
            logical_uid: UID in logical_devices table.

        Returns:
            Logical device name if found, otherwise None.
        """
        query = "SELECT name FROM logical_devices WHERE uid = %s"
        with psycopg2.connect() as conn, conn.cursor() as curs:
            curs.execute(query, (logical_uid,))
            row = curs.fetchone()
            if row is None:
                return None
            return row[0]


def _is_valid_json_object_key(name: Any) -> bool:
    """Validate that a value is a non-empty string usable as a JSON key.

    Args:
        name: Candidate key value.

    Returns:
        True when the value can be encoded as a JSON object key, else False.
    """
    if not isinstance(name, str) or not name:
        return False
    try:
        json.dumps({name: 0.0})
        return True
    except (TypeError, ValueError):
        return False


def _coerce_float(value: Any) -> Optional[float]:
    """Convert an arbitrary value to a finite float when possible.

    Args:
        value: Candidate value to convert.

    Returns:
        Float value when conversion succeeds and is finite, otherwise None.
    """
    if isinstance(value, bool):
        return None
    try:
        fval = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(fval):
        return None
    return fval


def _to_epoch_ms(value: Any) -> Optional[int]:
    """Convert supported timestamp representations to Unix epoch milliseconds.

    Args:
        value: Datetime, numeric epoch, or string timestamp value.

    Returns:
        Epoch time in milliseconds, or None if conversion fails.
    """
    if isinstance(value, datetime.datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return int(dt.timestamp() * 1000)

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        num = float(value)
        if not math.isfinite(num):
            return None
        # Assume values >= 1e11 are already milliseconds.
        if abs(num) >= 1e11:
            return int(num)
        return int(num * 1000)

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None

        numeric = _coerce_float(stripped)
        if numeric is not None:
            if abs(numeric) >= 1e11:
                return int(numeric)
            return int(numeric * 1000)

        try:
            iso = stripped.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return int(dt.timestamp() * 1000)
        except ValueError:
            return None

    return None


def _build_tb_gateway_payload_from_row(device_name: str, row: PhysicalTimeseriesRow) -> Optional[Dict[str, Any]]:
    """Build ThingsBoard gateway telemetry payload for one DB row.

    Args:
        device_name: Target ThingsBoard device name.
        row: Source physical_timeseries row.

    Returns:
        Gateway telemetry payload shaped as {device_name: [{ts, values}, ...]},
        or None if no valid telemetry entries remain after validation.
    """
    if not isinstance(row.json_msg, dict):
        logger.info("[db-skip] uid=%s json_msg is not an object.", row.uid)
        return None

    timeseries = row.json_msg.get("timeseries")
    if not isinstance(timeseries, list):
        logger.info("[db-skip] uid=%s json_msg.timeseries is not an array.", row.uid)
        return None

    now_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    msg_ts_ms = _to_epoch_ms(row.json_msg.get("timestamp"))
    if msg_ts_ms is not None and msg_ts_ms >= now_ms:
        logger.info(
            "[db-skip] uid=%s message timestamp is in the future: %r",
            row.uid,
            row.json_msg.get("timestamp"),
        )
        return None

    default_ts_ms = msg_ts_ms if msg_ts_ms is not None else _to_epoch_ms(row.ts)
    if default_ts_ms is None:
        logger.info("[db-skip] uid=%s no valid default timestamp.", row.uid)
        return None
    if default_ts_ms >= now_ms:
        logger.info("[db-skip] uid=%s default timestamp is in the future.", row.uid)
        return None

    grouped: Dict[int, Dict[str, float]] = {}
    for idx, item in enumerate(timeseries):
        if not isinstance(item, dict):
            logger.info("[db-skip] uid=%s dot[%s] is not an object.", row.uid, idx)
            continue

        dot_name = item.get("name")
        if not _is_valid_json_object_key(dot_name):
            logger.info("[db-skip] uid=%s dot[%s] invalid name: %r", row.uid, idx, dot_name)
            continue

        dot_value = _coerce_float(item.get("value"))
        if dot_value is None:
            logger.info("[db-skip] uid=%s dot[%s] invalid float value: %r", row.uid, idx, item.get("value"))
            continue

        if "timestamp" in item:
            ts_ms = _to_epoch_ms(item.get("timestamp"))
            if ts_ms is None:
                logger.info("[db-skip] uid=%s dot[%s] invalid timestamp: %r", row.uid, idx, item.get("timestamp"))
                continue
            if ts_ms >= now_ms:
                logger.info(
                    "[db-skip] uid=%s dot[%s] timestamp is in the future: %r",
                    row.uid,
                    idx,
                    item.get("timestamp"),
                )
                continue
        else:
            ts_ms = default_ts_ms

        grouped.setdefault(ts_ms, {})[dot_name] = dot_value

    if not grouped:
        logger.info("[db-skip] uid=%s no valid telemetry values after validation.", row.uid)
        return None

    telemetry = [{"ts": ts_ms, "values": values} for ts_ms, values in sorted(grouped.items())]
    return {device_name: telemetry}


def _parse_iso_date(value: str) -> datetime.date:
    """Parse command-line date argument in YYYY-MM-DD format.

    Args:
        value: Date string to parse.

    Returns:
        Parsed date object.

    Raises:
        argparse.ArgumentTypeError: If the value cannot be parsed as YYYY-MM-DD.
    """
    try:
        return datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date '{value}'. Use YYYY-MM-DD.") from exc


async def send_json_message(client: AsyncTlsMqttClient, topic: str, payload: Dict[str, Any]) -> None:
    """Publish dict payload to an MQTT topic as JSON.

    Args:
        client: Connected async MQTT client wrapper.
        topic: Destination MQTT topic.
        payload: JSON-serialisable payload object.

    Returns:
        None.

    Raises:
        ConnectionError: If MQTT connection drops unexpectedly.
        Exception: Propagates database monitoring failures.
    """
    await client.send_json(topic, payload)


async def _process_rows(
    client: AsyncTlsMqttClient,
    monitor: PhysicalTimeseriesMonitor,
    rows: List[PhysicalTimeseriesRow],
) -> None:
    """Process DB rows and publish valid telemetry to ThingsBoard.

    Args:
        client: Connected async MQTT client wrapper.
        monitor: Database monitor used for logical device lookups.
        rows: Rows to transform and publish.

    Returns:
        None.
    """
    for row in rows:
        device_name = await asyncio.to_thread(monitor.fetch_logical_device_name, row.logical_uid)
        if device_name is None:
            logger.info(
                "[db-skip] uid=%s logical_uid=%s not found in logical_devices.",
                row.uid,
                row.logical_uid,
            )
            continue

        payload = _build_tb_gateway_payload_from_row(device_name, row)
        if payload is None:
            continue

        await send_json_message(client, TB_GATEWAY_TELEMETRY_TOPIC, payload)
        logger.info(
            "[tb-sent] uid=%s logical_uid=%s device=%r points=%s",
            row.uid,
            row.logical_uid,
            device_name,
            sum(len(entry["values"]) for entry in payload[device_name]),
        )


def build_arg_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser for the utility script.

    Args:
        None.

    Returns:
        Configured argparse parser instance.
    """
    parser = argparse.ArgumentParser(description="Monitor MQTT topics over TLS and publish JSON asynchronously.")
    parser.add_argument("--host", required=True, help="MQTT broker hostname.")
    parser.add_argument("--port", type=int, default=8883, help="MQTT broker TLS port.")
    parser.add_argument("--topic", action="append", required=True, help="Topic filter to monitor. Repeat for more.")
    parser.add_argument("--topic-qos", type=int, default=1, choices=(0, 1, 2), help="QoS used for all subscriptions.")
    parser.add_argument("--client-id", default="", help="MQTT client id.")
    parser.add_argument("--username", help="MQTT username.")
    parser.add_argument("--password", help="MQTT password.")
    parser.add_argument("--ca-cert", help="Path to CA certificate PEM. Defaults to system trust store.")
    parser.add_argument("--cert-file", help="Path to client certificate PEM.")
    parser.add_argument("--key-file", help="Path to client private key PEM.")
    parser.add_argument("--insecure-tls", action="store_true", help="Disable server cert hostname verification.")
    parser.add_argument(
        "--db-poll-interval-seconds",
        type=float,
        default=300.0,
        help="Seconds between polls of physical_timeseries. Default: 300 (5 minutes).",
    )
    parser.add_argument(
        "--publish",
        metavar=("TOPIC", "JSON"),
        nargs=2,
        help='Optional one-shot JSON publish on startup, e.g. --publish "devices/me/telemetry" \'{"temp":21.3}\'',
    )
    parser.add_argument(
        "--from-date",
        type=_parse_iso_date,
        help="Process physical_timeseries rows from this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--to-date",
        type=_parse_iso_date,
        help="Process physical_timeseries rows through this date (YYYY-MM-DD).",
    )
    return parser


async def _print_messages(client: AsyncTlsMqttClient) -> None:
    """Continuously print received MQTT messages until task cancellation.

    Args:
        client: Connected async MQTT client wrapper.

    Returns:
        None.
    """
    while True:
        msg = await client.next_message()
        try:
            payload_view = msg.payload.decode("utf-8")
        except UnicodeDecodeError:
            payload_view = repr(msg.payload)
        logger.info(
            "[recv] topic=%s qos=%s retain=%s payload=%s",
            msg.topic,
            msg.qos,
            msg.retain,
            payload_view,
        )


async def _monitor_physical_timeseries(
    client: AsyncTlsMqttClient,
    monitor: PhysicalTimeseriesMonitor,
    stop_event: asyncio.Event,
) -> None:
    """Poll database rows and forward mapped telemetry to ThingsBoard gateway API.

    Args:
        client: Connected async MQTT client used to publish TB gateway telemetry.
        monitor: Database monitor used for row polling and device name lookups.
        stop_event: Event used to request graceful shutdown.

    Returns:
        None.

    Raises:
        Exception: Propagates database and MQTT publish failures.
    """
    await monitor.initialise_checkpoint()
    logger.info(
        "Postgres monitor started for physical_timeseries where logical_uid is not null (poll=%.1fs).",
        monitor.poll_interval_seconds,
    )

    while not stop_event.is_set():
        rows = await monitor.poll_new_rows()
        await _process_rows(client, monitor, rows)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=monitor.poll_interval_seconds)
        except asyncio.TimeoutError:
            pass


async def main() -> None:
    """Program entrypoint for MQTT + Postgres monitoring workflow.

    Args:
        None.

    Returns:
        None.
    """
    args = build_arg_parser().parse_args()
    if args.to_date is not None and args.from_date is None:
        raise SystemExit("--to-date requires --from-date.")
    if args.from_date is not None and args.to_date is None:
        args.to_date = datetime.date.today()
    if args.from_date is not None and args.to_date is not None and args.to_date < args.from_date:
        raise SystemExit("--to-date must be on or after --from-date.")

    topics = [(topic, args.topic_qos) for topic in args.topic]

    client = AsyncTlsMqttClient(
        host=args.host,
        port=args.port,
        topics=topics,
        client_id=args.client_id,
        username=args.username,
        password=args.password,
        ca_cert=args.ca_cert,
        cert_file=args.cert_file,
        key_file=args.key_file,
        insecure_tls=args.insecure_tls,
    )

    stop_event: Optional[asyncio.Event] = None
    printer_task: Optional[asyncio.Task] = None
    db_task: Optional[asyncio.Task] = None
    mqtt_disconnect_task: Optional[asyncio.Task] = None
    signal_task: Optional[asyncio.Task] = None

    await client.connect()
    try:
        logger.info("Connected to mqtts://%s:%s", args.host, args.port)
        logger.info("Subscribed to:")
        for topic, qos in topics:
            logger.info("  - %s (qos=%s)", topic, qos)

        if args.publish:
            publish_topic, json_text = args.publish
            payload = json.loads(json_text)
            await send_json_message(client, publish_topic, payload)
            logger.info("[sent] topic=%s payload=%s", publish_topic, json.dumps(payload))

        db_monitor = PhysicalTimeseriesMonitor(poll_interval_seconds=args.db_poll_interval_seconds)

        if args.from_date is not None:
            logger.info(
                "Processing physical_timeseries rows for date range %s to %s.",
                args.from_date.isoformat(),
                args.to_date.isoformat(),
            )
            total_rows = 0
            current_date = args.from_date
            while current_date <= args.to_date:
                logger.info("Processing day %s.", current_date.isoformat())
                rows = await db_monitor.fetch_rows_in_date_range(current_date, current_date)
                await _process_rows(client, db_monitor, rows)
                total_rows += len(rows)
                logger.info("Completed day %s. Rows read: %s", current_date.isoformat(), len(rows))
                current_date += datetime.timedelta(days=1)

            logger.info("Completed one-shot date-range processing. Total rows read: %s", total_rows)
            return

        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        printer_task = asyncio.create_task(_print_messages(client))
        db_task = asyncio.create_task(_monitor_physical_timeseries(client, db_monitor, stop_event))
        mqtt_disconnect_task = asyncio.create_task(client.wait_for_disconnect())
        signal_task = asyncio.create_task(stop_event.wait())

        done, pending = await asyncio.wait(
            {printer_task, db_task, mqtt_disconnect_task, signal_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        if signal_task in done:
            return

        for task in done:
            if task is signal_task:
                continue
            exc = task.exception()
            if exc is not None:
                raise exc
            raise RuntimeError("Background task exited unexpectedly.")
    finally:
        if stop_event is not None:
            stop_event.set()

        tasks_to_cancel = [printer_task, db_task, mqtt_disconnect_task, signal_task]
        for task in tasks_to_cancel:
            if task is not None:
                task.cancel()

        await asyncio.gather(*(task for task in tasks_to_cancel if task is not None), return_exceptions=True)
        await client.close()
        logger.info("Disconnected.")


if __name__ == "__main__":
    asyncio.run(main())
