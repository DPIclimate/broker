import pytest
import timescale.test.GenerateMsg as genmsg
import timescale.Timescale as ts
import json
import dateutil
import pika
import time

# 
def TestSingleInsertSpeed():
    message = ts.parse_json(json.loads(genmsg.random_msg_single()))
    starttime = time.time()
    if ts.insert_lines(message) == 1:
        endtime = time.time()
        finaltime = endtime - starttime
        print(f"Time for single insert: {finaltime}")
    else:
        print(f"Single Insert failed")
    

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
            messages.append(ts.parse_json(json.loads(line)))
            line_count += 1
            if line_count >= 10000:
                break

    starttime = time.time()
    print(len(messages))
    for msg in messages:
        if ts.insert_lines(msg) == 0:
            print(f"Bulk Insert failed")
            return
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







