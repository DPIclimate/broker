import pika
import json


def as_str(message: str = 'sent via RabbitMQ', host_name: str = 'localhost', queue_name: str = 'test') -> str: 
    connection = pika.BlockingConnection(pika.ConnectionParameters(host_name))
    channel = connection.channel()
    channel.queue_declare(queue=queue_name)
    channel.basic_publish(exchange='', routing_key=queue_name, body=message)
    connection.close()
    return(f"sent: '{message}'")


def as_json(message: str = {'id': 0, 'msg':'sent via RabbitMQ'}, host_name: str = 'localhost', queue_name: str = 'test') -> str: 
    return as_str(json.dumps(message), host_name, queue_name)
