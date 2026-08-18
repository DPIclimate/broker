"""Pure field mapping and conversion for ICT MQTT cache rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

import BrokerConstants


Converter = Callable[[str], Any]


class FieldMappingError(ValueError):
    """A field layout or cached row cannot be converted."""


@dataclass(frozen=True)
class Field:
    """Map a zero-based cache-file position to an IoTa value and conversion."""

    position: int
    converter: Converter = float


# Field positions include the correlation ID and device name at positions 0
# and 1. These definitions are copied from doc/ict_mqtt/design.md.
FIELD_MAPPINGS: dict[str, dict[str, Field]] = {
    "mncm2l_A": {
        BrokerConstants.TIMESTAMP_KEY: Field(2, str),
        "battV": Field(3, lambda value: int(value) / 1000),
        "solV": Field(4, lambda value: int(value) / 1000),
        "awq-c4e temperature": Field(14, float),
        "awq-c4e salinity": Field(16, float),
    },
    "mncm2l_B": {
        BrokerConstants.TIMESTAMP_KEY: Field(2, str),
        "battV": Field(3, lambda value: int(value) / 1000),
        "solV": Field(4, lambda value: int(value) / 1000),
        "c4e temperature": Field(14, float),
        "c4e salinity": Field(16, float),
    },
    "mncm3p_A": {
        BrokerConstants.TIMESTAMP_KEY: Field(2, str),
        "battV": Field(4, lambda value: int(value) / 1000),
        "solV": Field(5, lambda value: int(value) / 1000),
        "c4e-temperature": Field(15, float),
        "c4e-salinity": Field(17, float),
    },
}


DEVICE_LAYOUT_MAP: dict[str, str] = {
    "mncm2l301": "mncm2l_A",
    "mncm2l302": "mncm2l_A",
    "mncm2l303": "mncm2l_B",
    "mncm2l304": "mncm2l_B",
    "mncm2l305": "mncm2l_B",
    "mncm2l306": "mncm2l_B",
    "mncm2l307": "mncm2l_B",
    "mncm2l308": "mncm2l_B",
    "mncm2l309": "mncm2l_B",
    "mncm2l30a": "mncm2l_B",
}


def validate_field_mappings() -> None:
    """Reject unknown layout names before conversion starts."""
    unknown = sorted(set(DEVICE_LAYOUT_MAP.values()) - set(FIELD_MAPPINGS))
    if unknown:
        raise FieldMappingError(f"Unknown ICT MQTT field mappings: {', '.join(unknown)}")


def field_mapping_for_device(device_name: str) -> Mapping[str, Field] | None:
    """Return the named layout for a device, or None if no layout exists."""
    layout_name = DEVICE_LAYOUT_MAP.get(device_name)
    if layout_name is None:
        return None
    try:
        return FIELD_MAPPINGS[layout_name]
    except KeyError as error:
        raise FieldMappingError(
            f"Device {device_name!r} refers to unknown field mapping {layout_name!r}"
        ) from error


def translate_cache_fields(
    cache_fields: Sequence[str], mapping: Mapping[str, Field]
) -> dict[str, Any]:
    """Translate one complete cached CSV row into an IoTa message dictionary."""
    if len(cache_fields) < 3:
        raise FieldMappingError("A cached row must contain at least three fields")
    readings: list[dict[str, Any]] = []
    timestamp: str | None = None
    for name, field in mapping.items():
        if field.position >= len(cache_fields):
            # Some supplied messages omit an entire trailing sensor block.
            continue
        raw_value = cache_fields[field.position].strip()
        try:
            value = field.converter(raw_value)
        except (TypeError, ValueError, OverflowError) as error:
            raise FieldMappingError(f"Invalid {name!r} value {raw_value!r}: {error}") from error
        if name == BrokerConstants.TIMESTAMP_KEY:
            timestamp = str(value)
        else:
            readings.append({"name": name, "value": value})
    if timestamp is None:
        raise FieldMappingError("The field mapping did not produce a timestamp")
    if not readings:
        raise FieldMappingError("The field mapping produced no readings")
    return {
        BrokerConstants.CORRELATION_ID_KEY: cache_fields[0],
        BrokerConstants.TIMESTAMP_KEY: timestamp,
        BrokerConstants.TIMESERIES_KEY: readings,
    }
