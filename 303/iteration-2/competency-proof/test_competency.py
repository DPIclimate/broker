import pytest
import receive
import db
import send
import pika
import json
import random
import time

#helper to delete queues, as functions only consume a single message,
#tests can fail by retrieving a different message previously sent
def delete_queues(h, q):
    connection = pika.BlockingConnection(pika.ConnectionParameters(h))
    channel = connection.channel()
    channel.queue_delete(queue=q)
    connection.close()


#test sending/receiving via rabbitmq as a string
def test_receive_as_str():
    msg = 'test_message'
    host = 'localhost'
    queue = 'test_queue'
    delete_queues(host, queue)
    send.as_str(msg, host, queue)
    rec = receive.as_str(host, queue)
    assert rec == msg


#test sending/receiving via rabbitmq json objects
def test_receive_as_json():
    msg = {'id':0, 'msg':'test_message'}
    host = 'localhost'
    queue = 'test_queue'
    delete_queues(host, queue)
    send.as_json(msg, host, queue)
    rec = receive.as_json(host, queue)
    assert rec == msg


#questDB insert via line protocol
def test_db_insert():
    name = 'test_db'
    symbols = {'device':'test_device', 'type':'test_type'}
    columns = {'test_data': 12345}
    db.insert_line_protocol(name, symbols, columns, 'localhost', 9009)


#questDB query last 
def test_db_query():
    name = 'test_db'
    query = f'SELECT * FROM {name} LIMIT -1'
    testdata = random.randint(1,100000)

    #make an insert
    symbols = {'device':'test_device', 'type':'test_type'}
    columns = {'test_data': testdata}
    db.insert_line_protocol(name, symbols, columns, 'localhost', 9009)

    time.sleep(1)   #sleep to prevent previous insert

    #query last insert
    response = db.get_http_query(query, 'localhost', 9000)
    json_response = json.loads(response.text)
    assert json_response['dataset'][0][0] == 'test_device'
    assert json_response['dataset'][0][2] == testdata


#convert json message to line protocol format
#sends json response from rabbitmq -> receiver -> questdb and then checks that insert was good
def test_json_to_line():
    host = 'localhost'
    queue = 'test_queue'
    testdata = random.randint(1,100000)
    msg = {
        'name': 'test_db',
        'symbols': {'device':'test_device', 'type':'test_type'},
        'columns': {'test_data':testdata},
        'hostname': host,
        'port' : 9009
    }
    delete_queues(host, queue)
    send.as_json(msg, host, queue)
    receive.json_insert_line_protocol(host, queue)

    time.sleep(1)   #if no sleep then it will be too quick and get previous insert

    last = db.get_last_insert('test_db')
    assert int(last.split(',')[5]) == testdata


#test api ability to retrieve data from def funcname(self, parameter_list):
def test_api_retrieve_from_db():
    #send query to python function and return list of nodes
    #i.e something like
    #query = select from {table} between these tiems x, y
    #response = api.query_db(table, query, localhost, port)
    #assert response == expected data
    pass



