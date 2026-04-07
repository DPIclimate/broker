#!/usr/bin/env python3
"""ThingsBoard delivery implementation using DeliveryDbReader + MQTT transport."""

import datetime
import json
import logging
import math
import ssl
import threading
from typing import Any, Dict, List, Optional, Tuple

try:
    import paho.mqtt.client as mqtt
except ModuleNotFoundError as exc:
    raise SystemExit("Missing dependency: paho-mqtt. Install with: pip install paho-mqtt") from exc

try:
    from db_reader import DeliveryDbReader, PhysicalTimeseriesRow
except ModuleNotFoundError:  # pragma: no cover - used when imported as a package module
    from .db_reader import DeliveryDbReader, PhysicalTimeseriesRow


TB_GATEWAY_ATTRIBUTES_TOPIC = 'v1/gateway/attributes'
TB_GATEWAY_TELEMETRY_TOPIC = 'v1/gateway/telemetry'
TB_ATTRIBUTE_TYPES = {
    'BATTERY_VOLTAGE': 'Battery Voltage',
    'SOLAR_VOLTAGE': 'Solar Voltage',
}

logger = logging.getLogger(__name__)


class SyncTlsMqttClient:
    """Blocking MQTT client wrapper for ThingsBoard delivery."""

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
        """Initialise the MQTT client.

        Args:
            host: MQTT broker hostname.
            port: MQTT broker TLS port.
            topics: Subscriptions to establish after connect.
            client_id: MQTT client identifier.
            username: Optional MQTT username.
            password: Optional MQTT password.
            keepalive: MQTT keepalive interval in seconds.
            ca_cert: Optional path to CA cert file.
            cert_file: Optional path to client certificate file.
            key_file: Optional path to client private key file.
            insecure_tls: Disable TLS hostname verification when true.
            connect_timeout: Seconds to wait for connect acknowledgement.
            publish_timeout: Seconds to wait for publish acknowledgement.

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

        self._connect_event = threading.Event()
        self._disconnect_event = threading.Event()
        self._connect_error: Optional[str] = None
        self._disconnect_reason: Optional[Any] = None
        self._closing = False
        self._connected = False

    @staticmethod
    def _connect_reason_is_success(reason_code: Any) -> bool:
        """Interpret paho reason code object/value across API variants.

        Args:
            reason_code: Paho reason code object/value.

        Returns:
            True when reason indicates successful connect.
        """
        if hasattr(reason_code, "is_failure"):
            return not bool(reason_code.is_failure)
        try:
            return int(reason_code) == 0
        except (TypeError, ValueError):
            return str(reason_code).lower() in {"success", "0"}

    def connect(self) -> None:
        """Connect MQTT and wait for connect acknowledgement.

        Args:
            None.

        Returns:
            None.

        Raises:
            TimeoutError: If broker does not acknowledge connection in time.
            ConnectionError: If connect/subscription setup fails.
        """
        self._connect_event.clear()
        self._disconnect_event.clear()
        self._connect_error = None
        self._disconnect_reason = None
        self._closing = False
        self._connected = False

        self._client.connect_async(self.host, self.port, self.keepalive)
        self._client.loop_start()

        if not self._connect_event.wait(self.connect_timeout):
            self._client.loop_stop()
            raise TimeoutError("Timed out waiting for MQTT connection.")

        if self._connect_error:
            self.close()
            raise ConnectionError(self._connect_error)

    def close(self) -> None:
        """Disconnect MQTT and stop paho network thread.

        Args:
            None.

        Returns:
            None.
        """
        self._closing = True
        if self._client.is_connected():
            self._client.disconnect()
            self._disconnect_event.wait(timeout=2.0)
        self._client.loop_stop()
        self._connected = False

    def assert_healthy(self) -> None:
        """Raise when MQTT transport has failed.

        Args:
            None.

        Returns:
            None.

        Raises:
            ConnectionError: If broker disconnected unexpectedly.
        """
        if self._disconnect_event.is_set() and not self._closing:
            raise ConnectionError(f"MQTT connection lost: {self._disconnect_reason}")

    def send_json(self, topic: str, payload: Dict[str, Any]) -> None:
        """Publish JSON payload to a topic and wait for acknowledgement.

        Args:
            topic: Destination MQTT topic.
            payload: JSON-serialisable object.

        Returns:
            None.

        Raises:
            RuntimeError: If not connected or publish call fails.
            TypeError: If payload is not a dict.
            TimeoutError: If publish acknowledgement times out.
            ConnectionError: If connection drops unexpectedly.
        """
        if not self._connected:
            raise RuntimeError("Client is not connected.")
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dict.")

        data = json.dumps(payload, separators=(",", ":"))
        publish_info = self._client.publish(topic, data, qos=1, retain=False)
        if publish_info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"publish failed with code {publish_info.rc}")

        publish_info.wait_for_publish(timeout=self.publish_timeout)
        if not publish_info.is_published():
            raise TimeoutError("Timed out waiting for MQTT publish acknowledgement.")

        self.assert_healthy()

    def has_topic_subscriptions(self) -> bool:
        """Return whether topic subscriptions are configured.

        Args:
            None.

        Returns:
            True when topic subscriptions were configured.
        """
        return len(self.topics) > 0

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        """Paho connect callback.

        Args:
            client: Paho client.
            userdata: Paho userdata (unused).
            flags: Connect flags (unused).
            reason_code: Connect result.
            properties: MQTT v5 properties (unused).

        Returns:
            None.
        """
        if self._connect_reason_is_success(reason_code):
            self._connected = True
            for topic, qos in self.topics:
                result, _ = client.subscribe(topic, qos=qos)
                if result != mqtt.MQTT_ERR_SUCCESS:
                    self._connect_error = f"Failed to subscribe to topic '{topic}'."
                    break
        else:
            self._connect_error = f"MQTT connect failed with reason code {reason_code}."

        self._connect_event.set()

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        """Paho disconnect callback.

        Args:
            client: Paho client.
            userdata: Paho userdata (unused).
            disconnect_flags: Disconnect flags (unused).
            reason_code: Disconnect reason.
            properties: MQTT v5 properties (unused).

        Returns:
            None.
        """
        self._connected = False
        self._disconnect_reason = reason_code
        self._disconnect_event.set()

    def _on_message(self, client, userdata, msg):
        """Paho message callback for optional topic monitoring.

        Args:
            client: Paho client.
            userdata: Paho userdata (unused).
            msg: MQTT message object.

        Returns:
            None.
        """
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


class ThingsBoardDelivery(DeliveryDbReader):
    """Concrete DeliveryDbReader implementation for ThingsBoard via MQTT."""

    def __init__(self):
        """Initialise ThingsBoard delivery implementation.

        Args:
            None.

        Returns:
            None.
        """
        super().__init__(poll_interval_seconds=300.0)
        self._startup_publish: Optional[Tuple[str, str]] = None
        self._mqtt: Optional[SyncTlsMqttClient] = None

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        """Coerce value to finite float.

        Args:
            value: Candidate scalar.

        Returns:
            Float value when valid, otherwise None.
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

    @staticmethod
    def _to_epoch_ms(value: Any) -> Optional[int]:
        """Convert supported timestamp representations to epoch milliseconds.

        Args:
            value: Datetime, numeric epoch, or ISO-like string.

        Returns:
            Epoch milliseconds, or None when conversion fails.
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
            if abs(num) >= 1e11:
                return int(num)
            return int(num * 1000)

        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None

            numeric = ThingsBoardDelivery._coerce_float(stripped)
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

    @staticmethod
    def _build_tb_gateway_payloads_from_row(
        device_name: str,
        row: PhysicalTimeseriesRow,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Build ThingsBoard gateway telemetry and attribute payloads from one DB row.

        Args:
            device_name: ThingsBoard device name.
            row: Source physical_timeseries row.

        Returns:
            Tuple of telemetry payload and attribute payload.
        """
        if not isinstance(row.json_msg, dict):
            logger.info("[db-skip] uid=%s json_msg is not an object.", row.uid)
            return None, None

        timeseries = row.json_msg.get("timeseries")
        if not isinstance(timeseries, list):
            logger.info("[db-skip] uid=%s json_msg.timeseries is not an array.", row.uid)
            return None, None

        now_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
        msg_ts_ms = ThingsBoardDelivery._to_epoch_ms(row.json_msg.get("timestamp"))
        if msg_ts_ms is not None and msg_ts_ms >= now_ms:
            logger.info(
                "[db-skip] uid=%s message timestamp is in the future: %r",
                row.uid,
                row.json_msg.get("timestamp"),
            )
            return None, None

        default_ts_ms = msg_ts_ms if msg_ts_ms is not None else ThingsBoardDelivery._to_epoch_ms(row.ts)
        if default_ts_ms is None:
            logger.info("[db-skip] uid=%s no valid default timestamp.", row.uid)
            return None, None
        if default_ts_ms >= now_ms:
            logger.info("[db-skip] uid=%s default timestamp is in the future.", row.uid)
            return None, None

        grouped: Dict[int, Dict[str, float]] = {}
        latest_attributes: Dict[str, Tuple[int, float]] = {}
        for idx, item in enumerate(timeseries):
            if not isinstance(item, dict):
                logger.info("[db-skip] uid=%s dot[%s] is not an object.", row.uid, idx)
                continue

            dot_name = item.get("name")
            if not isinstance(dot_name, str) or not dot_name:
                logger.info("[db-skip] uid=%s dot[%s] invalid name: %r", row.uid, idx, dot_name)
                continue
            try:
                json.dumps({dot_name: 0.0})
            except (TypeError, ValueError):
                logger.info("[db-skip] uid=%s dot[%s] invalid name: %r", row.uid, idx, dot_name)
                continue

            dot_value = ThingsBoardDelivery._coerce_float(item.get("value"))
            if dot_value is None:
                logger.info(
                    "[db-skip] uid=%s dot[%s] invalid float value: %r",
                    row.uid,
                    idx,
                    item.get("value"),
                )
                continue

            if "timestamp" in item:
                ts_ms = ThingsBoardDelivery._to_epoch_ms(item.get("timestamp"))
                if ts_ms is None:
                    logger.info(
                        "[db-skip] uid=%s dot[%s] invalid timestamp: %r",
                        row.uid,
                        idx,
                        item.get("timestamp"),
                    )
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

            dot_type = item.get('type')
            if dot_type:
                attribute_name = TB_ATTRIBUTE_TYPES.get(dot_type.strip())
                if attribute_name is not None:
                    current_attribute = latest_attributes.get(attribute_name)
                    if current_attribute is None or ts_ms >= current_attribute[0]:
                        latest_attributes[attribute_name] = (ts_ms, dot_value)

        if not grouped:
            logger.info("[db-skip] uid=%s no valid telemetry values after validation.", row.uid)
            return None, None

        telemetry = [{"ts": ts_ms, "values": values} for ts_ms, values in sorted(grouped.items())]
        attribute_values = {
            attribute_name: value
            for attribute_name, (_, value) in sorted(latest_attributes.items())
        }
        attribute_payload = {device_name: attribute_values} if attribute_values else None
        return {device_name: telemetry}, attribute_payload

    def parser_description(self) -> str:
        """Return parser description text.

        Args:
            None.

        Returns:
            Parser description text.
        """
        return "Read from physical_timeseries and send to ThingsBoard."

    def add_subclass_args(self, parser) -> None:
        """Add ThingsBoard/MQTT-specific CLI arguments.

        Args:
            parser: Parser to extend.

        Returns:
            None.
        """
        parser.add_argument("--host", required=True, help="MQTT broker hostname.")
        parser.add_argument("--port", type=int, default=8883, help="MQTT broker TLS port.")
        parser.add_argument("--topic", action="append", default=[], help="Optional topic filter to monitor.")
        parser.add_argument("--topic-qos", type=int, default=1, choices=(0, 1, 2), help="QoS used for subscriptions.")
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
            help='Optional one-shot publish on startup, e.g. --publish "devices/me/telemetry" \'{"temp":21.3}\'',
        )

    def apply_runtime_args(self, args) -> None:
        """Apply parsed CLI args to runtime state.

        Args:
            args: Parsed CLI args.

        Returns:
            None.
        """
        self.poll_interval_seconds = args.db_poll_interval_seconds
        self._startup_publish = args.publish
        topics = [(topic, args.topic_qos) for topic in args.topic]
        self._mqtt = SyncTlsMqttClient(
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

    def connect_transport(self) -> None:
        """Connect MQTT transport and perform optional startup publish.

        Args:
            None.

        Returns:
            None.
        """
        if self._mqtt is None:
            raise RuntimeError("Transport is not configured. apply_runtime_args must run first.")
        self._mqtt.connect()
        logger.info("Connected to mqtts://%s:%s", self._mqtt.host, self._mqtt.port)
        if self._mqtt.has_topic_subscriptions():
            logger.info("Subscribed to:")
            for topic, qos in self._mqtt.topics:
                logger.info("  - %s (qos=%s)", topic, qos)

        if self._startup_publish is not None:
            publish_topic, json_text = self._startup_publish
            payload = json.loads(json_text)
            self._mqtt.send_json(publish_topic, payload)
            logger.info("[sent] topic=%s payload=%s", publish_topic, json.dumps(payload))

    def close_transport(self) -> None:
        """Close MQTT transport.

        Args:
            None.

        Returns:
            None.
        """
        if self._mqtt is None:
            return
        self._mqtt.close()

    def check_transport_health(self) -> None:
        """Raise when MQTT transport has failed.

        Args:
            None.

        Returns:
            None.
        """
        if self._mqtt is None:
            raise RuntimeError("Transport is not configured. apply_runtime_args must run first.")
        self._mqtt.assert_healthy()

    def deliver_row(self, row: PhysicalTimeseriesRow, logical_device_name: str) -> None:
        """Transform DB row to TB gateway payload and publish.

        Args:
            row: Source DB row.
            logical_device_name: Resolved logical device name.

        Returns:
            None.
        """
        if self._mqtt is None:
            raise RuntimeError("Transport is not configured. apply_runtime_args must run first.")
        telemetry_payload, attribute_payload = self._build_tb_gateway_payloads_from_row(logical_device_name, row)
        if telemetry_payload is None and attribute_payload is None:
            return

        if attribute_payload is not None:
            self._mqtt.send_json(TB_GATEWAY_ATTRIBUTES_TOPIC, attribute_payload)
            logger.info(
                "[tb-sent-attributes] uid=%s logical_uid=%s device=%r attributes=%s",
                row.uid,
                row.logical_uid,
                logical_device_name,
                sorted(attribute_payload[logical_device_name].keys()),
            )

        if telemetry_payload is None:
            return

        self._mqtt.send_json(TB_GATEWAY_TELEMETRY_TOPIC, telemetry_payload)
        logger.info(
            "[tb-sent] uid=%s logical_uid=%s device=%r points=%s",
            row.uid,
            row.logical_uid,
            logical_device_name,
            sum(len(entry['values']) for entry in telemetry_payload[logical_device_name]),
        )


def main() -> None:
    """CLI entrypoint for ThingsBoard delivery.

    Args:
        None.

    Returns:
        None.
    """
    delivery = ThingsBoardDelivery()
    delivery.run()


if __name__ == "__main__":
    main()
