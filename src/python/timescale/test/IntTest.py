import pytest
import timescale.test.GenerateMsg as genmsg
import timescale.Timescale as ts
import json
import dateutil
import pika
import time

# Remove comment below to make auto cleanup of DB after test-run.
#@pytest.fixture(scope="session", autouse=True)
def cleanup():
    # Perform setup (Nothing here at the moment)
    yield 
    # Perform teardown (Remove data from the database)
    ts.remove_data_with_value()

# Used for LTSReader testing
def send_rabbitmq_msg(payload: str = ""):
    creds = pika.PlainCredentials('broker', 'CHANGEME')
    params = pika.ConnectionParameters('mq', credentials=creds)
    conn = pika.BlockingConnection(params)
    channel = conn.channel()

    queue_name = 'ltsreader_logical_msg_queue'
    properties = {'device': 1}
    if (payload == ""):
        payload = genmsg.random_msg_single()

    channel.basic_publish(exchange='', routing_key=queue_name, body=payload,
                        properties=pika.BasicProperties(headers=properties))
    conn.close()
    
# Integration Testing including database to confirm no errors enter:
def test_insert_data_from_message():
    message = json.loads(genmsg.random_msg_single("valid_insert1"))
    parsed_message = ts.parse_json(message)
    ts.insert_lines(parsed_message)

    json_data = ts.query_all_data()
    
    found_value = any(value == "valid_insert1" for obj in json_data for value in obj.values())
    assert found_value, "The value 'valid_insert1' was not found in the DB"
  
def test_insert_invalid_key_msg():
    inv_msg =  f"""{{
                    "broker_correlation_id": "invalid_data",
                    "abc": "dfs23",
                    "def": "24fs",
                    "timestamp": "2023-0f1-30Tfd06:21:56g32Z",
                    "timeseries": [
                    {{
                    "name": "battery (v)",
                    "value": "invalid_data"
                    }}
                    ]
                    }}"""
    
    message = json.loads(inv_msg)
    ts.parse_json(message)
    ts.insert_lines(message)
    json_data = ts.query_all_data()
    
    for obj in json_data:
            for key, value in obj.items():
                assert value != "invalid_data", f"Invalid data '{value}' for key '{key}' was inserted"

def test_insert_invalid_format_msg():
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
    
    with pytest.raises(json.JSONDecodeError):
        message = json.loads(inv_msg)
        ts.parse_json(message)
        ts.insert_lines(message)
        json_data = ts.query_all_data()
        
def test_insert_invalid_missing_timestamp_value():
    inv_msg =  f"""{{
                    "broker_correlation_id": "invalid_data",
                    "p_uid": 101,
                    "l_uid": 102,
                    "timestamp": "",
                    "timeseries": [
                        {{
                        "name": "battery (v)",
                        "value": "invalid_data"
                        }}
                    ]
                    }}"""
    
    with pytest.raises(dateutil.parser.ParserError):
        message = json.loads(inv_msg)
        ts.parse_json(message)
        ts.insert_lines(message)
        json_data = ts.query_all_data()

def test_insert_msg_missing_physid_key():
    inv_msg =  f"""{{
                    "broker_correlation_id": "invalid_data",
                    "l_uid": 102,
                    "timestamp": "2023-01-30T06:21:56Z",
                    "timeseries": [
                        {{
                        "name": "battery (v)",
                        "value": "invalid_data"
                        }}
                    ]
                    }}"""
    
    #with pytest.raises(TypeError):
    message = json.loads(inv_msg)
    ts.parse_json(message)
    ts.insert_lines(message)
    json_data = ts.query_all_data()

    for obj in json_data:
            for key, value in obj.items():
                assert value != "invalid_data", f"Invalid data '{value}' for key '{key}' was inserted"

# Integration including rabbitmq and listener.
def test_consume_rabbitmq_msg():
    send_rabbitmq_msg(genmsg.random_msg_single("valid_consume1"))
    time.sleep(1)
    json_data = ts.query_all_data()
    found_valid_data = any(value == "valid_consume1" for obj in json_data for value in obj.values())
    assert found_valid_data, "Valid data 'test_consume1' is missing, message wasn't consumed by TS_LTSReader"

def test_consume_rabbitmq_two_msg():
    send_rabbitmq_msg(genmsg.random_msg("valid_consume2", "valid_consume3"))
    time.sleep(1)
    json_data = ts.query_all_data()
    found_valid_data = any(value == "valid_consume2" for obj in json_data for value in obj.values())
    found_valid_data2 = any(value == "valid_consume3" for obj in json_data for value in obj.values())
    assert found_valid_data, "Valid data 'test_consume2' is missing, message wasn't consumed by TS_LTSReader"
    assert found_valid_data2, "Valid data 'test_consume3' is missing, message wasn't consumed by TS_LTSReader"

def test_consume_invalid_rabbitmq_msg():
    inv_msg =  f"""{{
                    "broker_correlation_id": "invalid_data",
                    "abc": "dfs23",
                    "def": "24fs",
                    "timestamp": "2023-0f1-30Tfd06:21:56g32Z",
                    "timeseries": [
                    {{
                    "name": "battery (v)",
                    "value": "invalid_consume1"
                    }}
                    ]
                    }}"""

    send_rabbitmq_msg(inv_msg)
    time.sleep(1)
    json_data = ts.query_all_data()
    for obj in json_data:
        for key, value in obj.items():
            assert value != "invalid_consume1", f"""Invalid data 'invalid_consume1' added, 
                                                    message was incorrectly consumed by TS_LTSReader"""
