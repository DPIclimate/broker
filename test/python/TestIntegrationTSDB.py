#requires test environment running
#python -m pytest TestIntegrationTSDB.py

import pytest,sys,os,json,dateutil,pika,time,subprocess,requests,psycopg2
current_dir = os.path.dirname(os.path.abspath(__file__))
module_path = os.path.abspath(os.path.join(current_dir, '../../src/python'))
sys.path.append(module_path)


exchange='lts_exchange'
queue='ltsreader_logical_msg_queue'
mq_user='broker'
mq_pass='CHANGEME'
end_point = 'http://0.0.0.0:5687'

#helper, easier to just send via cmdline
def send_msg(msg: str):
    command = [
        'docker', 'exec', 'test-mq-1', 'rabbitmqadmin',
        'publish', '-u', mq_user, '-p', mq_pass,
        f'exchange={exchange}', f'routing_key={queue}',
        f'payload={msg}', 'properties={}'
    ]
    return subprocess.run(command, capture_output=True, text=True)


def check_insert(puid: str, luid: str):
    response = requests.get(
        f"{end_point}/query/?query="
        "SELECT name, value "
        "FROM timeseries "
        f"WHERE p_uid = {puid} "
        f"AND l_uid = {luid} "
    )
    response.raise_for_status()
    return response.json()


def test_send_valid_msg():
    msg = """
    {
        "broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6",
        "p_uid": 1,
        "l_uid": 1,
        "timestamp": "2023-01-30T06:21:56Z",
        "timeseries": [
        {
            "name": "battery (v)",
            "value": 6.66
        }
        ]
    }
    """
    result = send_msg(msg)
    time.sleep(1)
    insert = check_insert("1", "1") ## NAME CHANGES TO BATTERY_V
    assert(result.stdout == "Message published\n")
    assert(insert[-1] == ['BATTERY_V', 6.66])


def test_send_invalid_msg():
    msg = """
    {
        "l_uid": 777,
        "timestamp": "2023-01-30T06:21:56Z",
        "timeseries": [
        {
        }
        ]
    }
    """
    result = send_msg(msg)
    time.sleep(1)
    insert = check_insert("777", "777") ## NAME CHANGES TO BATTERY_V
    assert(result.stdout == "Message published\n")
    assert(insert == [])


#check we can still send a message after a bad one
def test_send_valid_msg2():
    msg = """
    {
        "broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6",
        "p_uid": 2,
        "l_uid": 2,
        "timestamp": "2023-01-30T06:22:56Z",
        "timeseries": [
        {
            "name": "battery (v)",
            "value": 9.99
        },
        {
            "name": "teSt-name-voltage",
            "value": 2.99
        }
        ]
    }
    """
    result = send_msg(msg)
    time.sleep(1)
    insert = check_insert("2", "2") ## NAME CHANGES TO BATTERY_V
    assert(result.stdout == "Message published\n")
    assert(insert[-1] == ['TEST_NAME_V', 2.99])
    assert(insert[-2] == ['BATTERY_V', 9.99])
