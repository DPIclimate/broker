import pika
import timescale

host = 'localhost'  # the RabbitMQ hostname or IP address
port = 5672  # the RabbitMQ port number
queue_name = 'my_queue'  # the name of the queue you want to consume from

def callback(ch, method, properties, body):
    print(f"Received message: {body}")


if __name__ == "__main__":

    connection = pika.BlockingConnection(pika.ConnectionParameters(host=host, port=port))
    channel = connection.channel()

    channel.queue_declare(queue=queue_name)
    channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)


    print('Waiting for messages...')
    channel.start_consuming()