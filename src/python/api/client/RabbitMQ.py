#
# TODO:
#
# Add closed connection and re-connection callbacks so callers are aware these
# things happened. The webhook needs this information to tell it to reprocess
# cached message files.
#

# This code is based on the async examples in the pika github repo.
# See https://github.com/pika/pika/tree/master/examples

from multiprocessing import connection
from numbers import Integral
import pika, pika.spec
from pika.adapters.asyncio_connection import AsyncioConnection
from pika.exchange_type import ExchangeType

import asyncio, functools, json, logging, os

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
logger = logging.getLogger(__name__)

_EXCHANGE_NAME = 'broker_exchange'
_EXCHANGE_TYPE = ExchangeType.direct

# TODO: Find a good way of allowing callers to reference queue names symbolically
# rather than hard-coding the names. Probably a dict.
_QUEUE_NAMES = ['ttn_raw', 'physical_timeseries', 'logical_timeseries']

_user = os.environ['RABBITMQ_DEFAULT_USER']
_passwd = os.environ['RABBITMQ_DEFAULT_PASS']
_host = os.environ['RABBITMQ_HOST']
_port = os.environ['RABBITMQ_PORT']

_amqp_url_str = f'amqp://{_user}:{_passwd}@{_host}:{_port}/%2F'


class RabbitMQClient(object):

    def __init__(self, on_bind_ok=None, on_message=None, on_publish_ack=None):
        self._connection = None
        self._channel = None

        self._message_number = 0

        self._stopping = False
        self.stopped = False
        self._on_bind_ok = on_bind_ok
        self._on_message = on_message
        self._on_publish_ack = on_publish_ack

        # This is used to track how many queues have been bound during the
        # startup process. When all queues are bound the on_bind_ok callback
        # will be called.
        self._q_bind_count = 0

    async def connect(self, delay=0):
        """
        Initiate a connection to RabbitMQ. The connection is not valid until
        self.on_connection_open() is called.
        """
        if delay > 0:
            logger.info(f'Waiting for {delay}s before connection attempt.')
            await asyncio.sleep(delay)

        logger.info('Connecting to %s', _amqp_url_str)
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
        logger.info('Connection opened')
        self._connection = connection
        self.open_channel()

    def on_connection_open_error(self, _unused_connection, err):
        """
        Opening a connection failed. If the calling code has not requested
        a shutdown via self.stop() then try to reconnect.

        Consider backing off the delay to some maximum value.
        """
        logger.error('Connection open failed: %s', err)
        self._channel = None

        if not self._stopping:
            asyncio.create_task(self.connect(5))

    def on_connection_closed(self, _unused_connection, reason):
        """
        The connection has closed. If the calling code has not requested
        a shutdown via self.stop() then try to reconnect assuming the closure
        is due to an error.

        Consider backing off the delay to some maximum value.
        """
        logger.warning('Connection closed: %s', reason)
        self._channel = None

        if not self._stopping:
            asyncio.create_task(self.connect(5))
        else:
            self.stopped = True

    def stop(self) -> None:
        """
        Shut down the connection to RabbitMQ.

        Start by closing the channel. The channel closed callback
        will then ask to close the connection.
        """
        if self._stopping:
            return

        self._stopping = True
        self._channel.close()


    async def _close_connection(self) -> None:
        """
        Start closing the connection.
        
        This method should not be called from outside this class.
        """
        self._connection.close()


    def open_channel(self):
        logger.info('Creating a new channel')
        self._connection.channel(on_open_callback=self.on_channel_open)


    def on_channel_open(self, channel):
        logger.info('Channel opened')
        self._channel = channel
        self._message_number = 0
        logger.info('Adding channel close callback')
        self._channel.add_on_close_callback(self.on_channel_closed)

        logger.info('Issuing Confirm.Select RPC command')
        self._channel.confirm_delivery(self.on_delivery_confirmation)

        logger.info(f'Declaring exchange {_EXCHANGE_NAME}')
        self._channel.exchange_declare(
            exchange=_EXCHANGE_NAME,
            exchange_type=_EXCHANGE_TYPE,
            durable=True,
            callback=self.on_exchange_declareok)

    def on_channel_closed(self, channel, reason):
        logger.warning('Channel %i was closed: %s', channel, reason)
        self._channel = None

        if not self._stopping:
            if not (self._connection.is_closed or self._connection.is_closing):
                self.open_channel()
        else:
            asyncio.create_task(self._close_connection())


    def on_exchange_declareok(self, method):
        self._q_bind_count = 0
        for queue_name in _QUEUE_NAMES:
            logger.info(f'Declaring queue {queue_name}')
            self._channel.queue_declare(queue=queue_name, durable=True, callback=self.on_queue_declareok)


    def queue_declare(self, queue_name):
        logger.info(f'Declaring queue {queue_name}')
        # Note a durable queue is created so persistent messages can survive a
        # RabbitMQ server restart.
        self._channel.queue_declare(queue=queue_name, durable=True, callback=self.on_queue_declareok)

    def on_queue_declareok(self, q_declare_ok):
        queue_name = q_declare_ok.method.queue
        logger.info('Binding %s to %s with %s', _EXCHANGE_NAME, queue_name, queue_name)
        self._channel.queue_bind(queue_name, _EXCHANGE_NAME, routing_key=queue_name, callback=self.on_bindok)

    def on_bindok(self, _unused_frame):
        self._q_bind_count += 1

        if len(_QUEUE_NAMES) == self._q_bind_count and self._on_bind_ok is not None:
            logger.info('All queues bound, calling on_bind_ok callback.')
            self._on_bind_ok()

    def start_listening(self, queue_name):
        """
        Callers use this method to indicate they wish to receive messages.

        The messages will be passed back to the caller via the on_message
        callback passed to the constructor of this class.
        """
        logger.info('Adding consumer cancellation callback')
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)
        self._consumer_tag = self._channel.basic_consume(queue_name, self._on_message)

    def on_consumer_cancelled(self, method_frame):
        logger.info('Consumer was cancelled remotely, shutting down: %r', method_frame)
        if self._channel:
            self._channel.close()

    def on_delivery_confirmation(self, method_frame):
        """
        pika calls this to notify that RabbitMQ has accepted a published message.

        The caller will be notified via the on_publish_ack callback passed to the
        constructor of this class.
        """
        if self._on_publish_ack is not None:
            asyncio.create_task(self._on_publish_ack(method_frame.method.delivery_tag))


    def publish_message(self, routing_key: str, message) -> Integral:
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

        self._channel.basic_publish(_EXCHANGE_NAME, routing_key,
                                    json.dumps(message, ensure_ascii=False),
                                    properties)
        self._message_number += 1
        return self._message_number


    def ack(self, delivery_tag: Integral) -> None:
        """
        Ack a message delivered by the on_message callback.

        RabbitMQ will keep a message on the queue until it has been ack'd.
        """
        if self._connection.is_open and self._channel is not None:
            self._channel.basic_ack(delivery_tag)
