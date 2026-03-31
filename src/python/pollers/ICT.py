"""ICT MQTT integration.

Subscribes to ICT Internationals provided MQTT broker/topic and forwards messages into the
broker pipeline using the same overall flow as `ydoc/Wombat.py`:
- parse payload (ICT topics are commonly CSV lines; some topics may be JSON)
- store the raw message in `raw_messages`
- create/update the corresponding `physical_devices` row
- publish the message to the `physical_timeseries` exchange after adding:
  - `broker_correlation_id`
  - `p_uid`

Configuration (env vars):
- `ICT_MQTT_HOST` (default: `ictcatm1.com`)
- `ICT_MQTT_PORT` (default: `1883`)
- `ICT_MQTT_TOPIC` (default: `ict/data/#`)

The device id is derived from the topic segment after `ict/data/`.
These names match those found when running the ICTEagleIO poller. 

Unsure if we can expect message names to be consistent across feeds as of yet.

"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import math
import signal
import uuid
from typing import Any, Optional, Tuple

import dateutil.parser
import paho.mqtt.client as mqtt
from pika.exchange_type import ExchangeType

import BrokerConstants
import api.client.DAO as dao
import api.client.RabbitMQ as mq
import util.LoggingUtil as lu
from pdmodels.Models import PhysicalDevice

std_logger = logging.getLogger(__name__)

finish = False

# RabbitMQ publishing
_tx_channel: Optional[mq.TxChannel] = None
_mq_client: Optional[mq.RabbitMQConnection] = None

# MQTT ingest
_mqtt_client: Optional[mqtt.Client] = None
_mqtt_queue: "asyncio.Queue[Tuple[str, bytes]]" = asyncio.Queue()
_event_loop: Optional[asyncio.AbstractEventLoop] = None


def _ensure_tz_aware(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def _extract_timestamp(msg: Any) -> datetime.datetime:
    if not isinstance(msg, dict):
        return datetime.datetime.now(datetime.timezone.utc)

    candidate_keys = (
        BrokerConstants.TIMESTAMP_KEY,
        "ts",
        "time",
        "datetime",
        "timestamp_utc",
        "received_at",
    )

    for key in candidate_keys:
        if key in msg and msg[key] is not None:
            try:
                return _ensure_tz_aware(dateutil.parser.isoparse(str(msg[key])))
            except Exception:
                continue

    return datetime.datetime.now(datetime.timezone.utc)


def _parse_csv_payload(payload_text: str) -> Optional[dict[str, Any]]:
    """Parse ICT CSV payloads into an IoTa-ish dict.

    Expected samples look like:
    "2026-03-30 05:38:00,4193,20960,...,23.177999,8.028400,..."

    Returns None if it doesn't look like a CSV payload.
    """
    line = payload_text.strip()
    if not line or "," not in line:
        return None

    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 2:
        return None

    try:
        # ICT sample uses a space separator and no timezone; treat as UTC.
        ts = dateutil.parser.parse(parts[0])
        ts = _ensure_tz_aware(ts)
    except Exception:
        return None

    values: list[Any] = []
    for p in parts[1:]:
        if p == "" or p.lower() == "nan":
            values.append(None)
            continue
        try:
            if any(ch in p for ch in (".", "e", "E")):
                v = float(p)
                if math.isnan(v):
                    v = None
                values.append(v)
            else:
                values.append(int(p))
        except Exception:
            values.append(p)

    dots = []
    for i, v in enumerate(values, start=1):
        dots.append({"name": f"v{i}", "value": v})

    return {
        BrokerConstants.TIMESTAMP_KEY: ts.isoformat().replace("+00:00", "Z"),
        BrokerConstants.TIMESERIES_KEY: dots,
        "csv": line,
        "values": values,
    }


def _device_id_from_topic(topic: str) -> str:
    # Expected: ict/data/<device_id>
    parts = topic.split("/")
    if len(parts) >= 3:
        return parts[-1]
    return topic


def sigterm_handler(sig_no, _stack_frame) -> None:
    """Handle SIGTERM from docker with an orderly shutdown."""
    global finish

    std_logger.info(f"{signal.strsignal(sig_no)}, setting finish to True")
    finish = True

    try:
        dao.stop()
    except Exception:
        std_logger.exception("DAO stop failed during shutdown")

    if _mq_client is not None:
        try:
            _mq_client.stop()
        except Exception:
            std_logger.exception("RabbitMQ stop failed during shutdown")

    if _mqtt_client is not None:
        try:
            _mqtt_client.loop_stop()
            _mqtt_client.disconnect()
        except Exception:
            std_logger.exception("MQTT disconnect failed during shutdown")


def _mqtt_on_connect(client: mqtt.Client, _userdata, _flags, reason_code, _properties=None) -> None:
    topic = os.getenv("ICT_MQTT_TOPIC", "ict/data/#")
    rc = getattr(reason_code, "value", reason_code)
    if rc == 0:
        std_logger.info(f"Connected to MQTT, subscribing to {topic}")
        client.subscribe(topic)
    else:
        std_logger.error(f"MQTT connect failed: reason_code={reason_code}")


def _mqtt_on_disconnect(_client: mqtt.Client, _userdata, reason_code, _properties=None) -> None:
    if reason_code != 0:
        std_logger.warning(f"MQTT disconnected unexpectedly: reason_code={reason_code}")


def _mqtt_on_message(_client: mqtt.Client, _userdata, mqtt_msg: mqtt.MQTTMessage) -> None:
    # paho callbacks happen in the network thread; hop to the asyncio loop.
    global _event_loop

    if _event_loop is None:
        return

    topic = mqtt_msg.topic
    payload = mqtt_msg.payload

    def _enqueue() -> None:
        try:
            _mqtt_queue.put_nowait((topic, payload))
        except Exception:
            std_logger.exception("Failed to enqueue MQTT message")

    _event_loop.call_soon_threadsafe(_enqueue)


async def _start_rabbitmq() -> None:
    global _mq_client, _tx_channel

    _tx_channel = mq.TxChannel(
        exchange_name=BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME,
        exchange_type=ExchangeType.fanout,
    )
    _mq_client = mq.RabbitMQConnection(channels=[_tx_channel])
    asyncio.create_task(_mq_client.connect())

    while not _tx_channel.is_open:
        await asyncio.sleep(0)


def _start_mqtt() -> None:
    global _mqtt_client

    host = os.getenv("ICT_MQTT_HOST", "ictcatm1.com")
    port = int(os.getenv("ICT_MQTT_PORT", "1883"))

    client_id = f"ict_listener_{uuid.uuid4()}"
    _mqtt_client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
    _mqtt_client.reconnect_delay_set(min_delay=1, max_delay=60)

    _mqtt_client.on_connect = _mqtt_on_connect
    _mqtt_client.on_disconnect = _mqtt_on_disconnect
    _mqtt_client.on_message = _mqtt_on_message

    std_logger.info(f"Connecting to MQTT {host}:{port} as {client_id}")
    _mqtt_client.connect_async(host=host, port=port, keepalive=60)
    _mqtt_client.loop_start()


async def _process_one(topic: str, payload: bytes) -> None:
    if _tx_channel is None or not _tx_channel.is_open:
        std_logger.warning("RabbitMQ tx channel not open; dropping message")
        return

    correlation_id = str(uuid.uuid4())

    # Parse payload
    try:
        payload_text = payload.decode("utf-8", errors="replace")
    except Exception:
        std_logger.info("Payload decode failed, ignoring message")
        return

    msg_obj: Any
    try:
        msg_obj = json.loads(payload_text)
    except Exception:
        csv_msg = _parse_csv_payload(payload_text)
        if csv_msg is None:
            std_logger.info("Payload parsing failed (not JSON/CSV), ignoring message")
            return
        msg_obj = csv_msg

    # Ensure we publish a dict message downstream.
    if not isinstance(msg_obj, dict):
        msg = {BrokerConstants.RAW_MESSAGE_KEY: msg_obj}
    else:
        msg = msg_obj

    msg_with_cid = {BrokerConstants.CORRELATION_ID_KEY: correlation_id, BrokerConstants.RAW_MESSAGE_KEY: msg}

    device_id = _device_id_from_topic(topic)

    if BrokerConstants.TIMESTAMP_KEY in msg:
        try:
            msg_ts = _ensure_tz_aware(dateutil.parser.parse(str(msg[BrokerConstants.TIMESTAMP_KEY])))
        except Exception:
            msg_ts = _extract_timestamp(msg)
    else:
        msg_ts = _extract_timestamp(msg)

    # Store the raw message first
    dao.add_raw_json_message(BrokerConstants.ICT, msg_ts, correlation_id, msg)

    lu.cid_logger.info(f"Accepted MQTT message for {device_id}", extra=msg_with_cid)

    # Upsert the physical device
    # Include both the device id and the topic for operator visibility.
    source_ids = {"device_id": device_id, "topic": topic}

    # Ensure `source_ids` exists in the message (used downstream by SCMN wrangling).
    msg.setdefault("source_ids", {})
    if isinstance(msg["source_ids"], dict):
        msg["source_ids"].setdefault("device_id", device_id)
        msg["source_ids"].setdefault("topic", topic)

    pds = dao.get_pyhsical_devices_using_source_ids(BrokerConstants.ICT, {"device_id": device_id})
    if len(pds) < 1:
        lu.cid_logger.info("Device not found, creating physical device.", extra=msg_with_cid)

        props = {
            BrokerConstants.CREATION_CORRELATION_ID_KEY: correlation_id,
            BrokerConstants.LAST_MSG: msg,
        }

        device_name = f"{device_id}"
        pd = PhysicalDevice(
            source_name=BrokerConstants.ICT,
            name=device_name,
            location=None,
            last_seen=msg_ts,
            source_ids=source_ids,
            properties=props,
        )
        pd = dao.create_physical_device(pd)
    else:
        pd = pds[0]
        pd.source_ids = source_ids
        pd.last_seen = msg_ts
        pd.properties[BrokerConstants.LAST_MSG] = msg
        pd = dao.update_physical_device(pd)

    if pd is None:
        lu.cid_logger.error(
            f"Physical device not found, message processing ends now. {correlation_id}",
            extra=msg_with_cid,
        )
        return

    lu.cid_logger.info(f"Using device id {pd.uid}", extra=msg_with_cid)

    # Forward the message into the pipeline (same pattern as Wombat.py)
    msg[BrokerConstants.CORRELATION_ID_KEY] = correlation_id
    msg[BrokerConstants.PHYSICAL_DEVICE_UID_KEY] = pd.uid
    msg.setdefault("mqtt_topic", topic)

    # Ensure a timestamp exists and is a string.
    if BrokerConstants.TIMESTAMP_KEY not in msg:
        msg[BrokerConstants.TIMESTAMP_KEY] = msg_ts.isoformat().replace("+00:00", "Z")
    else:
        msg[BrokerConstants.TIMESTAMP_KEY] = str(msg[BrokerConstants.TIMESTAMP_KEY])

    _tx_channel.publish_message("physical_timeseries", msg)


async def _process_loop() -> None:
    while not finish:
        try:
            topic, payload = await _mqtt_queue.get()
        except Exception:
            std_logger.exception("MQTT queue receive failed")
            await asyncio.sleep(1)
            continue

        try:
            await _process_one(topic, payload)
        except Exception:
            std_logger.exception("Error while processing MQTT message")


async def main() -> None:
    global _event_loop

    std_logger.info("===============================================================")
    std_logger.info("               STARTING ICT MQTT LISTENER")
    std_logger.info("===============================================================")

    _event_loop = asyncio.get_running_loop()

    # Ensure the source exists in the DB (idempotent) before messages arrive.
    try:
        dao.add_physical_source(BrokerConstants.ICT)
    except Exception:
        std_logger.exception("Failed adding ICT source")

    await _start_rabbitmq()
    _start_mqtt()

    asyncio.create_task(_process_loop())

    while not finish:
        await asyncio.sleep(2)

    # Allow RabbitMQ to close out
    while _mq_client is not None and not _mq_client.stopped:
        await asyncio.sleep(1)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, sigterm_handler)
    asyncio.run(main())
    std_logger.info("Exiting.")
