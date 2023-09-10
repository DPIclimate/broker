#requires test environment running
#python -m pytest TestIntegrationTSDB.py

import pytest,sys,os,json,dateutil,pika,time,subprocess,requests,psycopg2

current_dir = os.path.dirname(os.path.abspath(__file__))
module_path = os.path.abspath(os.path.join(current_dir, '../../src/python'))
sys.path.append(module_path)

tsdb_table = "timeseries"
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

def get_current_time():
    current_time = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    return current_time

def generate_and_send_message(correlation_id, p_uid, l_uid, timestamp, name, value):
    msg = {
        "broker_correlation_id": correlation_id,
        "p_uid": p_uid,
        "l_uid": l_uid,
        "timestamp": timestamp,
        "timeseries": [
            {
                "name": name,
                "value": value
            }
        ]
    }
    send_msg(json.dumps(msg))

def test_send_and_query_message():
    current_time = get_current_time()
    generate_and_send_message("test1", 1, 1, current_time, "battery (v)", 6.66)
    
    timeout = time.time() + 10
    while True:
        insert = check_insert("1", "1")
        if insert or time.time() > timeout:
            break
        time.sleep(0.2)
    
    assert insert['title'][-1] == ['BATTERY_V', 6.66]
    
    query_params = {"timestamp": current_time}
    response = requests.get(f"{end_point}/query/", params=query_params)
    response.raise_for_status()
    data = response.json()
    
    assert 'title' in data
    assert len(data['title']) > 0
    
    matching_rows = [row for row in data['title'] if row[3] == current_time]
    assert len(matching_rows) > 0
    assert matching_rows[0][3] == current_time

def test_query_by_time_range():
    current_time1 = get_current_time()
    generate_and_send_message("test1", 1, 1, current_time1, "battery (v)", 6.66)
    time.sleep(2)
    current_time2 = get_current_time()
    generate_and_send_message("test2", 1, 1, current_time2, "battery (v)", 9.99)
    time.sleep(1)
    
    query_params = {"timestamp1": current_time1, "timestamp2": current_time2}
    response = requests.get(f"{end_point}/query/", params=query_params)
    response.raise_for_status()
    data = response.json()
    
    assert 'title' in data
    assert len(data['title']) >= 2
    
    timestamps = [row[3] for row in data['title']]
    assert current_time1 in timestamps
    assert current_time2 in timestamps

def test_get_last_records_for_luid():
    current_time1 = get_current_time()
    generate_and_send_message("test1", 1, 1, current_time1, "battery (v)", 6.66)
    time.sleep(3)
    current_time2 = get_current_time()
    generate_and_send_message("test2", 1, 1, current_time2, "battery (v)", 9.99)
    time.sleep(3)
    
    response = requests.get(f"{end_point}/query/l_uid/1/last", params={"seconds": 10})
    response.raise_for_status()
    data = response.json()
    
    assert len(data) >= 2
    
    timestamps = [row[3] for row in data]
    assert current_time1 in timestamps
    assert current_time2 in timestamps


