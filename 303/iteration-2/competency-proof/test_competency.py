import pytest
import receive
import db
import send
import pika
import json
import random
import time
import subprocess
import sys
import requests


#helper to delete queues, as functions only consume a single message,
#tests can fail by retrieving a different message previously sent
def delete_queues(h, q):
    connection = pika.BlockingConnection(pika.ConnectionParameters(h))
    channel = connection.channel()
    channel.queue_delete(queue=q)
    connection.close()


#test sending/receiving via rabbitmq as a string
def test_receive_as_str(mqhost):
    msg = 'test_message'
    queue = 'test_queue'
    delete_queues(mqhost, queue)
    send.as_str(msg, mqhost, queue)
    rec = receive.as_str(mqhost, queue)
    assert rec == msg


#test sending/receiving via rabbitmq json objects
def test_receive_as_json(mqhost):
    msg = {'id':0, 'msg':'test_message'}
    queue = 'test_queue'
    delete_queues(mqhost, queue)
    send.as_json(msg, mqhost, queue)
    rec = receive.as_json(mqhost, queue)
    assert rec == msg


#questDB insert via line protocol
def test_db_insert(dbhost):
    name = 'test_db'
    symbols = {'device':'test_device', 'type':'test_type'}
    columns = {'test_data': 12345}
    db.insert_line_protocol(name, symbols, columns, dbhost, 9009)


#questDB query last 
def test_db_query(dbhost):
    name = 'test_db'
    query = f'SELECT * FROM {name} LIMIT -1'
    testdata = random.randint(1,100000)

    #make an insert
    symbols = {'device':'test_device', 'type':'test_type'}
    columns = {'test_data': testdata}
    db.insert_line_protocol(name, symbols, columns, dbhost, 9009)

    time.sleep(1)   #sleep to prevent previous insert

    #query last insert
    response = db.get_http_query(query, dbhost, 9000)
    json_response = json.loads(response.text)
    assert json_response['dataset'][0][0] == 'test_device'
    assert json_response['dataset'][0][2] == testdata


#convert json message to line protocol format
#sends json response from rabbitmq -> receiver -> questdb and then checks that insert was good
def test_json_to_line(dbhost, mqhost):
    queue = 'test_queue'
    testdata = random.randint(1,100000)
    msg = {
        'name': 'test_db',
        'symbols': {'device':'test_device', 'type':'test_type'},
        'columns': {'test_data':testdata},
        'hostname': dbhost,
        'port' : 9009
    }
    delete_queues(mqhost, queue)
    send.as_json(msg, mqhost, queue)
    receive.json_insert_line_protocol(mqhost, queue)

    time.sleep(1)   #if no sleep then it will be too quick and get previous insert

    last = db.get_last_insert('test_db', dbhost)
    assert int(last.split(',')[5]) == testdata

#check that we can pull from api
def test_api_is_alive(aphost):
    response = requests.get(f"http://{aphost}:8000/")
    assert response.status_code == 200
    assert response.json() == {"msg": "hi there!!"}


def test_api_curl_command(dbhost, aphost):
    # Puts prior DB entries out of range.
    time.sleep(2)
    testdata = random.randint(1,100000)
    testdata2 = random.randint(1,100000)

    # Make two inserts
    name = 'test_db'
    symbols = {'device':'test_device', 'type':'test_type'}

    columns = {'test_data': testdata}
    db.insert_line_protocol(name, symbols, columns, dbhost, 9009)
    columns2 = {'test_data': testdata2}
    db.insert_line_protocol(name, symbols, columns2, dbhost, 9009)

    # Make query via CLI
    url = f"http://{aphost}:8000/get/last/2?host={dbhost}"
    command = ["curl", url]
    output = subprocess.check_output(command)

    json_output = json.loads(output.decode('utf-8'))
    
    assert testdata == json_output[0][2]
    assert testdata2 == json_output[1][2]
