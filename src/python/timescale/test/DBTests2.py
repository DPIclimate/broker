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

def TestSingleInsertSpeed():
    message = send_rabbitmq_msg()
    starttime = time.time()
    while ts.query_num_entries() < 1:
        pass

    endtime = time.time()
    finaltime = endtime - starttime
    if ts.query_num_entries() > 1:
        print("Single insert found multiple entries, invalid result.")
    else:
        print(f"Time for single insert: {finaltime}")
    

# def TestBulkInsertSpeed():
#     starttime = time.time()
#     if ts.insert_data_to_db("timescale/test/msgs") == 1:
#         print(f"Issue with bulk insert test, data insert failed")
#         endtime = time.time()
#         finaltime = endtime - starttime
#         print(f"Time for bulk insert: {finaltime}")
#     else:
#         print(f"Bulk Insert failed")

def TestBulkInsertSpeed():
    filename = "timescale/test/msgs"
    messages = []
    with open(filename, 'r') as f:
        # for line in f:
        #     messages.append(ts.parse_json(json.loads(line)))
        line_count = 0
        for line in f:
            messages.append(line)
            line_count += 1
            if line_count >= 10000:
                break

    starttime = time.time()
    for msg in messages:
        send_rabbitmq_msg(msg)
    while ts.query_num_entries() < 53301:
        time.sleep(2) # Potential 2 second error. May entry speed
        pass
    endtime = time.time()
    finaltime = endtime - starttime
    print(f"Time for bulk insert: {finaltime}")

def TestQuerySpeed():
    starttime = time.time()
    ts.query_all_data()
    endtime = time.time()
    finaltime = endtime - starttime
    print(f"Time to query all data: {finaltime}")


if __name__ == "__main__":
    TestSingleInsertSpeed()
    TestBulkInsertSpeed()
    TestQuerySpeed()







