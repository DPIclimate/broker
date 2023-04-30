import logging
import pika
import os
import time
import timescale

# Set up logging
logging.basicConfig(level=logging.INFO)

# RabbitMQ connection parameters
user = os.getenv('RABBITMQ_DEFAULT_USER', 'broker')
password = os.getenv('RABBITMQ_DEFAULT_PASS', 'CHANGEME')
host = os.getenv('RABBITMQ_HOST', 'mq')
port = int(os.getenv('RABBITMQ_PORT', '5672'))
amqp_url_str = f'amqp://{user}:{password}@{host}:{port}/%2F'

# Set up RabbitMQ channel
connection = None
channel = None
while connection is None:
    try:
        connection = pika.BlockingConnection(pika.URLParameters(amqp_url_str))
        channel = connection.channel()
        logging.info('Connected to RabbitMQ')
    except:
        logging.warning('Failed to connect to RabbitMQ, retrying...')
        time.sleep(10)

# Declare queue
queue_name = 'ubidots_logical_msg_queue'
channel.queue_declare(queue=queue_name, durable=True)
logging.info(f'Declared queue {queue_name}')

# Set up message callback
def callback(ch, method, properties, body):
    logging.info(f'Received message: {body}')
    json_str = timescale.parse_json_string(str(body, 'utf-8'))
    timescale.insert_lines(json_str)

# Consume messages
logging.info('Waiting for messages...')
channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
try:
    channel.start_consuming()
except KeyboardInterrupt:
    channel.stop_consuming()

# Clean up
logging.info('Closing connection...')
connection.close()
logging.info('Connection closed.') 
