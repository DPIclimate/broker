import pytest
import timescale.test.GenerateMsg as genmsg
import timescale.Timescale as ts
import json
import dateutil
import pika
import time

# 
def TestSingleInsertSpeed():
    message = genmsg.random_msg_single
    starttime = time.time()
    ts.insert_lines(message)
    endtime = time.time()
    finaltime = endtime - starttime
    print(f"Time for single insert: {finaltime}")

def TestBulkInsertSpeed():
    messages = []
    for i in range(1000):
        message = genmsg.random_msg_single()
        messages.append(message)

    starttime = time.time()
    for i in messages:
        insert = ts.insert_lines(i)
        if insert == 0:
            print(f"Issue with bulk insert test, data insert failed")
            return
    endtime = time.time()
    finaltime = endtime - starttime
    print(f"Time for bulk insert: {finaltime}")

def TestQuerySpeed():
    starttime = time.time()
    ts.query_all_data()
    endtime = time.time()
    finaltime = endtime - starttime
    print(f"Time for single insert: {finaltime}")


if __name__ == "__main__":
    TestSingleInsertSpeed()
    TestBulkInsertSpeed()







