#
# TODO:
#
# Add closed connection and re-connection callbacks so callers are aware these
# things happened. The webhook needs this information to tell it to reprocess
# cached message files.
#

# This code is based on the async examples in the pika github repo.
# See https://github.com/pika/pika/tree/master/examples

import pika, pika.channel, pika.spec
from pika.adapters.asyncio_connection import AsyncioConnection
from pika.exchange_type import ExchangeType

import asyncio, json, logging, os
from enum import Enum, auto

_user = os.environ['RABBITMQ_DEFAULT_USER']
_passwd = os.environ['RABBITMQ_DEFAULT_PASS']
_host = os.environ['RABBITMQ_HOST']
_port = os.environ['RABBITMQ_PORT']

_amqp_url_str = f'amqp://{_user}:{_passwd}@{_host}:{_port}/%2F'

class State(Enum):
    OPENING = auto()
    OPEN = auto()
    CLOSING = auto()
    CLOSED = auto()


class RabbitMQConnection(object):
    """ ======================================================================
    A RabbitMQConnection wraps a RabbitMQ connection and includes code to
    re-open the connection if it closes or the open fails.
    ====================================================================== """
    def __init__(self, channels):
        self._connection = None
        self.state = State.OPENING

        self._stopping = False
        self.stopped = False

        self.channels = channels
        logging.debug(f'given channels {self.channels}')


    async def connect(self, delay=0):
        """
        Initiate a connection to RabbitMQ. The connection is not valid until
        self.on_connection_open() is called.
        """
        self.state = State.OPENING
        if delay > 0:
            logging.debug(f'Waiting for {delay}s before connection attempt.')
            await asyncio.sleep(delay)

        logging.info(f'Connecting to {_host} as {_user}')
        return AsyncioConnection(
            pika.URLParameters(_amqp_url_str),
            on_open_callback=self.on_connection_open,
            on_open_error_callback=self.on_connection_open_error,
            on_close_callback=self.on_connection_closed)


    def on_connection_open(self, connection):
        """
        Now the connection is open a channel can be opened. Channels
        are 'virtual connections' where all operations are performed.
        """
        logging.info('Connection opened')
        self._connection = connection
        self.state = State.OPEN

        for z in self.channels:
            logging.info(f'Opening channel {z}, of type {type(z)}')
            z.open(self._connection)


    def on_connection_open_error(self, _unused_connection, err):
        """
        Opening a connection failed. If the calling code has not requested
        a shutdown via self.stop() then try to reconnect.

        Consider backing off the delay to some maximum value.
        """
        logging.error('Connection open failed: %s', err)
        if not self._stopping:
            asyncio.create_task(self.connect(30))
        else:
            self.state = State.CLOSED


    def on_connection_closed(self, _unused_connection, reason):
        """
        The connection has closed. If the calling code has not requested
        a shutdown via self.stop() then try to reconnect assuming the closure
        is due to an error.

        Consider backing off the delay to some maximum value.
        """
        logging.warning('Connection closed: %s', reason)
        for z in self.channels:
            z.is_open = False

        if not self._stopping:
            asyncio.create_task(self.connect(60))
        else:
            self.state = State.CLOSED
            self.stopped = True


    def stop(self) -> None:
        """
        Shut down the connection to RabbitMQ.

        Start by closing the channel. The channel closed callback
        will then ask to close the connection.
        """
        if self._stopping or self.stopped:
            return

        self._stopping = True
        self.state = State.CLOSING

        # This closes the channels automatically.
        self._connection.close()


class TxChannel(object):
    """ ======================================================================
    A TxChannel wraps a RabbitMQ channel devoted to publishing messages to a
    single exchange.
    ====================================================================== """
    def __init__(self, exchange_name, exchange_type, on_ready=None, on_publish_ack=None):
        self._exchange_name = exchange_name
        self._exchange_type = exchange_type
        self._on_ready = on_ready
        self._on_publish_ack = on_publish_ack

        self._channel: pika.channel.Channel = None
        self._message_number = 0
        self.is_open = False


    def open(self, connection) -> None:
        connection.channel(on_open_callback=self.on_channel_open)


    def on_channel_open(self, channel):
        logging.debug(f'Opened tx channel {channel} to server {_amqp_url_str}')
        self._channel = channel
        self._message_number = 0
        self._channel.add_on_close_callback(self.on_channel_closed)
        self._channel.confirm_delivery(self.on_delivery_confirmation)

        logging.debug(f'Declaring exchange {self._exchange_name}')
        self._channel.exchange_declare(
            exchange=self._exchange_name,
            exchange_type=self._exchange_type,
            durable=True,
            callback=self.on_exchange_declareok)


    def on_channel_closed(self, channel, reason):
        logging.debug(f'Channel {channel} to exchange {self._exchange_name} was closed: {reason}')
        self._channel = None
        self.is_open = False


    def on_exchange_declareok(self, method):
        logging.info(f'Exchange {self._exchange_name} declared ok, ready to send.')
        self.is_open = True
        if self._on_ready is not None:
            asyncio.create_task(self._on_ready(self))


    def publish_message(self, routing_key: str, message) -> int:
        """
        Publish a message to RabbitMQ.

        The message cannot be considered safely accepted by RabbitMQ until
        the on_publish_ack callback passed to the constructor of this class
        has been called.

        All messages are published persistently so they can survive a
        RabbitMQ server restart. The server is not meant to ack receipt
        of a message until it has been written to disk.
        """
        if self._channel is None or not self._channel.is_open:
            return

        properties = pika.BasicProperties(
            app_id='broker',
            content_type='application/json',
            delivery_mode = pika.spec.PERSISTENT_DELIVERY_MODE
            )

        self._channel.basic_publish(self._exchange_name, routing_key,
                                    json.dumps(message, ensure_ascii=False),
                                    properties)
        self._message_number += 1
        return self._message_number


    def on_delivery_confirmation(self, method_frame):
        """
        pika calls this to notify that RabbitMQ has accepted a published message.

        The caller will be notified via the on_publish_ack callback passed to the
        constructor of this class.
        """
        if self._on_publish_ack is not None:
            asyncio.create_task(self._on_publish_ack(method_frame.method.delivery_tag))


class RxChannel(object):
    """ ======================================================================
    An RxChannel wraps a RabbitMQ channel devoted to receiving messages from a
    single exchange. A durable queue is declared.

    routing_key is not required for fanout exchanges, but must be set for
    direct exchanges.
    ====================================================================== """
    def __init__(self, exchange_name, exchange_type, queue_name, on_message, routing_key=None):
        self._exchange_name = exchange_name
        self._exchange_type = exchange_type
        self._queue_name = queue_name
        self._routing_key = routing_key
        self._on_message = on_message

        self._channel: pika.channel.Channel = None
        self.is_open = False


    def open(self, connection) -> None:
        connection.channel(on_open_callback=self.on_channel_open)


    def on_channel_open(self, channel):
        logging.debug(f'Opened rx channel {channel} to server {_amqp_url_str}')
        self._channel = channel
        self._channel.add_on_close_callback(self.on_channel_closed)

        logging.debug(f'Declaring exchange {self._exchange_name}')
        self._channel.exchange_declare(
            exchange=self._exchange_name,
            exchange_type=self._exchange_type,
            durable=True,
            callback=self.on_exchange_declareok)


    def on_channel_closed(self, channel, reason):
        logging.warning(f'Channel {channel} to exchange {self._exchange_name} was closed: {reason}')
        self._channel = None
        self.is_open = False


    def on_exchange_declareok(self, method):
        logging.debug(f'Exchange {self._exchange_name} declared ok, declaring queue {self._queue_name}.')
        self._channel.queue_declare(queue=self._queue_name, durable=True, callback=self.on_queue_declareok)


    def on_queue_declareok(self, q_declare_ok):
        logging.debug(f'Binding queue {self._queue_name} to exchange {self._exchange_name} with routing key {self._routing_key}')
        self._channel.queue_bind(self._queue_name, self._exchange_name, routing_key=self._routing_key, callback=self.on_bindok)


    def on_bindok(self, _unused_frame):
        logging.info('Adding channel cancellation callback, start listening for messages.')
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)
        self._consumer_tag = self._channel.basic_consume(self._queue_name, self._on_message)
        self.is_open = True


    def on_consumer_cancelled(self, method_frame):
        logging.warning('Consumer was cancelled remotely, shutting down: %r', method_frame)
        if self._channel and self._channel.is_open:
            self._channel.close()
            self.is_open = False
