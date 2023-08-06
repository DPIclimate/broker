import pytest
import timescale.test.GenerateMsg as genmsg
import timescale.Timescale as ts
import json
import dateutil
import time


# Unit testing:
# Confirms capability to read message containing two sets of timeseries data.
def test_extract_data_from_msg():
    message = json.loads(genmsg.random_msg("valid_value1", "valid_value2"))
    parsed_message = ts.parse_json(message)
    print(parsed_message)
    assert parsed_message[0][5] == "valid_value1"
    assert parsed_message[1][5] == "valid_value2"

# Confirms capability for message format with only one set of timeseries data.
def test_extract_data_from_single_msg():
    message = json.loads(genmsg.random_msg_single("valid_value"))
    parsed_message = ts.parse_json(message)
    print(parsed_message)
    assert parsed_message[0][5] == "valid_value"

# Confirms empty list is returned in the case of a key error
def test_extract_invalid_keys():
    inv_msg =  f"""{{
                    "broker_correlation_id": "invalid_data",
                    "abc": "dfs23",
                    "def": "24fs",
                    "timestamp": "2023-01-30T06:21:56Z",
                    "timeseries": [
                    {{
                    "name": "battery (v)",
                    "value": "invalid_data"
                    }}
                    ]
                    }}"""
    
    result = ts.parse_json_string(inv_msg)
    assert result == []


# Confirms empty list is returned in the case of a format error
def test_extract_invalid_format_msg(caplog):
    inv_msg =  f"""{{
                    "broker_correlation_id": "invalid_data",
                    "p_uid": 101,
                    "l_uid": 102,
                    "timestamp": "2023-01-30T06:21:56Z",
                    "timeseries": [
                        {{
                        "name" "battery (v)",
                        "value" invalid_data
                        }}
                    ]
                    }}"""
    
    result = ts.parse_json_string(inv_msg)
    assert result == []

