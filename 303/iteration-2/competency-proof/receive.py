import pika
import json
import db

def as_bytes(host_name: str = 'localhost', queue_name: str = 'test') -> bytes:
    connection = pika.BlockingConnection(pika.ConnectionParameters(host_name))
    channel = connection.channel()
    channel.queue_declare(queue=queue_name)
    method_frame, header_frame, body = channel.basic_get(queue = queue_name)        

    if method_frame is None:
        connection.close()
        return ''
    else:            
        channel.basic_ack(delivery_tag=method_frame.delivery_tag)
        connection.close() 
        return body


def as_str(host_name: str = 'localhost', queue_name: str = 'test') -> str:
        return as_bytes(host_name, queue_name).decode("utf-8")


def as_json(host_name: str = 'localhost', queue_name: str = 'test') -> str:
    return json.loads(as_bytes(host_name, queue_name))


def json_insert_line_protocol(host_name: str = 'localhost', queue_name: str = 'test') -> str:
    body = as_json(host_name, queue_name)
    name = body['name']
    symbols = body['symbols']
    columns = body['columns']
    db.insert_line_protocol(body['name'], body['symbols'], body['columns'], body['hostname'], body['port'])
