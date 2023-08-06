import logging
import pika
import os
import time
import timescale

# Set logging level (INFO should suffice)
logging.basicConfig(level=logging.INFO)

# RabbitMQ connection parameters, defaults based on .env (kind of unecessary)
user = os.getenv('RABBITMQ_DEFAULT_USER', 'broker')
password = os.getenv('RABBITMQ_DEFAULT_PASS', 'CHANGEME')
host = os.getenv('RABBITMQ_HOST', 'mq')
port = int(os.getenv('RABBITMQ_PORT', '5672'))
amqp_url_str = f'amqp://{user}:{password}@{host}:{port}/%2F'

# Connection to RabbitMQ channel
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

# Defining the queue to receive from (likely to be changed going forward)
queue_name = 'ubidots_logical_msg_queue'
channel.queue_declare(queue=queue_name, durable=True)
logging.info(f'Declared queue {queue_name}')

# Method used in message callback
def handle_message(ch, method, properties, body):
    logging.info(f'Received message: {body}')
    json_str = timescale.parse_json_string(str(body, 'utf-8'))
    timescale.insert_lines(json_str)
    channel.basic_ack()

# Consume messages from queue, and handle them using handle_message.
logging.info('Awaiting messages...')
channel.basic_consume(queue=queue_name, on_message_callback=handle_message, auto_ack=False)
try:
    channel.start_consuming()
except KeyboardInterrupt:
    channel.stop_consuming()

# Close of the connection upon program interrupt.
logging.info('Closing connection...')
connection.close()
logging.info('Connection closed.') 
