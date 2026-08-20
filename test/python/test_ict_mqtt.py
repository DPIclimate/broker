import csv
import json
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from receiver.ict_mqtt.main import (
    CachedMessage,
    Config,
    ConfirmingPublisher,
    DEVICE_LAYOUT_MAP,
    DiskCache,
    FIELD_MAPPINGS,
    ICT_EAGLEIO_DEVICE_NAMES,
    InvalidMessage,
    ICTMQTTReceiver,
    JsonMessageWriter,
    device_name_from_topic,
    field_mapping_for_device,
    normalize_timestamp,
    retry_delay,
    translate,
)


SAMPLE = (
    b"2026-08-15 10:49:39,4161,0,0,152,805498,12261,210498,"
    b"0,0,0,0,15.733000,52412.000000,34.515999,34177.000000"
)


def test_cache_writes_the_specified_csv_format(tmp_path):
    cache = DiskCache(tmp_path)
    cache.prepare()

    path, cached = cache.store("mncm2l307", SAMPLE)

    assert path.name.startswith("mncm2l307_2026-08-15T10:49:39+00:00_")
    assert path.suffix == ".csv"
    uuid.UUID(cached.correlation_id)
    with path.open(newline="") as stream:
        fields = next(csv.reader(stream))
    assert fields[:3] == [cached.correlation_id, "mncm2l307", "2026-08-15T10:49:39+00:00"]
    assert cache.load(path) == cached


def test_translate_applies_known_conversions():
    cached = CachedMessage(
        str(uuid.uuid4()),
        "mncm2l307",
        tuple(next(csv.reader([SAMPLE.decode()])).copy()),
    )
    values = list(cached.values)
    values[0] = "2026-08-15T10:49:39Z"
    cached = CachedMessage(cached.correlation_id, cached.device_name, tuple(values))

    message = translate(cached, field_mapping_for_device(cached.device_name))

    assert message["timestamp"] == "2026-08-15T10:49:39Z"
    assert {"name": "battV", "value": 4.161} in message["timeseries"]
    assert {"name": "solV", "value": 0.0} in message["timeseries"]
    assert {"name": "c4e temperature", "value": 15.733} in message["timeseries"]
    assert {"name": "c4e salinity", "value": 34.515999} in message["timeseries"]


def test_raw_message_strips_cache_metadata():
    cached = CachedMessage(
        "38fa1db4-8d53-455f-8898-5d577b024156",
        "mncm2l307",
        ("2026-08-15T10:49:39Z", "4161", "0"),
    )

    assert cached.raw_message() == {
        "timestamp": "2026-08-15T10:49:39Z",
        "broker_correlation_id": "38fa1db4-8d53-455f-8898-5d577b024156",
        "raw_msg": "2026-08-15T10:49:39Z,4161,0",
    }


def test_translate_accepts_an_omitted_trailing_sensor_block():
    cached = CachedMessage(
        str(uuid.uuid4()),
        "mncm2l303",
        ("2026-08-15T10:49:39Z", "4181", "0", "0", "213", "675684",
         "96996", "339355", "0", "0", "0", "0"),
    )

    message = translate(cached, field_mapping_for_device(cached.device_name))

    assert {"name": "battV", "value": 4.181} in message["timeseries"]
    assert not any(reading["name"].startswith("c4e ") for reading in message["timeseries"])


def test_invalid_timestamp_is_not_cached(tmp_path):
    cache = DiskCache(tmp_path)
    cache.prepare()

    with pytest.raises(InvalidMessage):
        cache.store("mncm2l307", b"not-a-time,1,2")


def test_unmapped_device_message_is_moved_to_rejected(tmp_path):
    cache = DiskCache(tmp_path / "cache")
    cache.prepare()
    path, _cached = cache.store("mncm1k708", SAMPLE)
    config = Config(
        mqtt_server="localhost",
        mqtt_port=1883,
        mqtt_keepalive=60,
        cache_dir=cache.root,
        test_mode=True,
        test_message_dir=tmp_path / "messages",
        amqp_url=None,
    )
    receiver = ICTMQTTReceiver(config, cache)

    receiver._process_file(path)

    rejected_path = cache.rejected / path.name
    assert not path.exists()
    assert rejected_path.exists()
    assert rejected_path.with_suffix(".error.txt").read_text() == "No field mapping.\n"


def test_normalize_timestamp_accepts_any_datetime_format_python_can_parse():
    parsed = normalize_timestamp("2026-08-15T20:49:39+10:00")

    assert parsed.isoformat() == "2026-08-15T20:49:39+10:00"


def test_topic_and_retry_contract(monkeypatch):
    assert device_name_from_topic("ict/data/mncm2l307") == "mncm2l307"
    assert "mncm2l307" in ICT_EAGLEIO_DEVICE_NAMES
    with pytest.raises(InvalidMessage):
        device_name_from_topic("ict/data/mncm2l307/extra")
    monkeypatch.setattr("receiver.ict_mqtt.main.random.uniform", lambda _start, _end: 4.0)
    assert retry_delay(1) == 0
    assert retry_delay(2) == 64


def test_publisher_services_data_events_when_connected():
    publisher = ConfirmingPublisher("amqp://guest:guest@localhost:5672/%2F")
    publisher.connection = Mock(is_closed=False)

    publisher.process_data_events()

    publisher.connection.process_data_events.assert_called_once_with(time_limit=0)


def test_test_mode_configuration_does_not_require_rabbitmq(monkeypatch, tmp_path):
    monkeypatch.setenv("ICT_MQTT_SERVER", "localhost")
    monkeypatch.setenv("ICT_MQTT_DISK_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("ICT_MQTT_TEST", "1")
    monkeypatch.setenv("ICT_TEST_MSG_DIR", str(tmp_path / "messages"))
    for name in (
        "RABBITMQ_URL", "RABBITMQ_DEFAULT_USER", "RABBITMQ_DEFAULT_PASS",
        "RABBITMQ_HOST", "RABBITMQ_PORT",
    ):
        monkeypatch.delenv(name, raising=False)

    config = Config.from_environment()

    assert config.test_mode is True
    assert config.amqp_url is None
    assert config.cache_dir == tmp_path / "cache"
    assert config.test_message_dir == tmp_path / "messages"


def test_test_mode_writes_json_and_removes_cache_file(tmp_path):
    cache = DiskCache(tmp_path / "cache")
    cache.prepare()
    path, cached = cache.store("mncm2l307", SAMPLE)
    config = Config(
        mqtt_server="localhost",
        mqtt_port=1883,
        mqtt_keepalive=60,
        cache_dir=cache.root,
        test_mode=True,
        test_message_dir=tmp_path / "messages",
        amqp_url=None,
    )
    writer = JsonMessageWriter(config.test_message_dir)
    writer.prepare()
    receiver = ICTMQTTReceiver(config, cache, test_writer=writer)

    receiver._process_file(path)

    output_path = config.test_message_dir / path.with_suffix(".json").name
    assert not path.exists()
    assert output_path.exists()
    message = json.loads(output_path.read_text())
    assert message["broker_correlation_id"] == cached.correlation_id
    assert message["timestamp"] == "2026-08-15T10:49:39+00:00"
    assert "p_uid" not in message


def test_production_stores_raw_message_as_json(monkeypatch, tmp_path):
    cache = DiskCache(tmp_path / "cache")
    cache.prepare()
    path, cached = cache.store("mncm2l307", SAMPLE)
    config = Config(
        mqtt_server="localhost",
        mqtt_port=1883,
        mqtt_keepalive=60,
        cache_dir=cache.root,
        test_mode=False,
        test_message_dir=None,
        amqp_url="amqp://guest:guest@localhost:5672/%2F",
    )
    publisher = Mock()
    dao = Mock()
    device = SimpleNamespace(uid=42, last_seen=None, properties={})
    dao.update_physical_device.return_value = device
    monkeypatch.setattr("receiver.ict_mqtt.main._dao", lambda: dao)
    receiver = ICTMQTTReceiver(config, cache, publisher=publisher)
    receiver.devices[cached.device_name] = device
    monkeypatch.setattr(receiver, "_device", Mock(return_value=device))

    receiver._process_file(path)

    raw_message = cached.raw_message()
    dao.add_raw_json_message.assert_called_once_with(
        "ict_mqtt", cached.timestamp, cached.correlation_id, raw_message, device.uid
    )
    assert device.properties["last_msg"] == raw_message
    publisher.publish.assert_called_once()
    assert not path.exists()
