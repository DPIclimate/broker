import pytest
import timescale.test.GenerateMsg as genmsg
import timescale.Timescale as ts
import json
import dateutil
import pika
import time

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

def send_rabbitmq_bulk(payload: str = ""):
    creds = pika.PlainCredentials('broker', 'CHANGEME')
    params = pika.ConnectionParameters('mq', credentials=creds)
    conn = pika.BlockingConnection(params)
    channel = conn.channel()

    queue_name = 'bulky_ts_queue'
    properties = {'device': 1}
    if (payload == ""):
        payload = genmsg.random_msg_single()

    channel.basic_publish(exchange='', routing_key=queue_name, body=payload,
                        properties=pika.BasicProperties(headers=properties))
    conn.close()


def TestSingleInsertSpeed(filename: str = 'timescale/test/msgs/msgs', target_msgs: int = 53300):
    messages = []
    with open(filename, 'r') as f:
        # for line in f:
        #     messages.append(ts.parse_json(json.loads(line)))
        line_count = 0
        for line in f:
            messages.append(line)
            line_count += 1
            if line_count >= 100:
                break

    starttime = time.time()
    for msg in messages:
        send_rabbitmq_msg(msg)
    while ts.query_num_entries() < target_msgs:
        time.sleep(2) # Potential 2 second error. May entry speed
        pass
    endtime = time.time()
    finaltime = endtime - starttime
    print(f"Time for single insert: {finaltime}")

def TestBulkInsertSpeed(filename: str = 'timescale/test/msgs/msgs', target_msgs: int = 53300):
    msgs = ""  # Initialize as an empty string

    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    num_lines = len(lines)
    for idx, line in enumerate(lines):
        # Skip empty lines
        if not line.strip():
            continue
            
        # Add a comma after each line except the last line
        msgs += line.strip()
        if idx < num_lines - 1:
            msgs += ","

    # Construct the JSON string
    msgs = f'{{"data":[{msgs}]}}'
    starttime = time.time()
    send_rabbitmq_bulk(msgs)

    while ts.query_num_entries() < target_msgs:
        time.sleep(2)  # Potential 2-second error for polling.
        pass
    endtime = time.time()
    finaltime = endtime - starttime
    print(f"Time for bulk insert: {finaltime}")

# def TestBulkInsertSpeed():
#     filename = "timescale/test/msgs"
#     msgs = f"""{{"data":["""
#     with open(filename, 'r') as f:
#         line_count = 0
#         for line in f:
#             msgs += line
#             msgs += ','
#             line_count += 1
#             if line_count >= 10:
#                 break
#             msgs += "]}"
#     print(msgs)
#     starttime = time.time()
#     # send_rabbitmq_bulk(messages)
#     json_msgs = json.loads(msgs)
#     parsed_msgs = []
#     for line in json_msgs["data"]:
#         parsed_msgs.append(ts.parse_json(line))
#     ts.insert_lines_bulk(parsed_msgs)

#     while ts.query_num_entries() < 53300:
#         time.sleep(2) # Potential 2 second error for polling.
#         pass
#     endtime = time.time()
#     finaltime = endtime - starttime
#     print(f"Time for bulk insert: {finaltime}")

# def TestBulkInsertSpeed():
#     filename = "timescale/test/msgs"
#     msgs = ""  # Initialize as an empty string
#     with open(filename, 'r') as f:
#         line_count = 0
#         for line in f:
#             # Skip empty lines
#             if not line.strip():
#                 continue
#             msgs += line.strip()
#             line_count += 1
#             if line_count >= 10:
#                 break
#             msgs += ','  # Add a comma after each line except the last line

#     # Construct the JSON string
#     msgs = f'{{"data":[{msgs}]}}'

#     print(msgs)  # For testing purposes, to check the constructed JSON

#     time.sleep(2)

#     starttime = time.time()
#     parsed_msgs = []
#     for line in json.loads(msgs)["data"]:
#         parsed_msgs.append(ts.parse_json(line))
#     ts.insert_lines_bulk(parsed_msgs)

#     while ts.query_num_entries() < 53300:
#         time.sleep(2)  # Potential 2-second error for polling.
#         pass
#     endtime = time.time()
#     finaltime = endtime - starttime
#     print(f"Time for bulk insert: {finaltime}")
    
def TestQuerySpeed():
    starttime = time.time()
    ts.query_all_data()
    endtime = time.time()
    finaltime = endtime - starttime
    print(f"Time to query all data: {finaltime}")

def cleardb():
    ts.remove_data_with_value()
    time.sleep(0.2)


if __name__ == "__main__":
    cleardb()
    print("Single insert 1:")
    TestSingleInsertSpeed('timescale/test/msgs/single_msgs1', 2)
    cleardb()
    print("Single insert 2:")
    TestSingleInsertSpeed('timescale/test/msgs/single_msgs2', 48)
    cleardb()
    print("Single insert 3:")
    TestSingleInsertSpeed('timescale/test/msgs/single_msgs3', 480)
    cleardb()
    print("Bulk insert 1:")
    TestBulkInsertSpeed('timescale/test/msgs/bulk_msgs1', 480)
    cleardb()
    print("Bulk insert 2:")
    TestBulkInsertSpeed('timescale/test/msgs/bulk_msgs2', 5330)
    cleardb()
    print("Bulk insert 3:")
    TestBulkInsertSpeed('timescale/test/msgs/bulk_msgs3', 53300)
    TestQuerySpeed()








