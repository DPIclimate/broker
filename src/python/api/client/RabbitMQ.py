from numbers import Integral
import pika, pika.spec
from pika.adapters.asyncio_connection import AsyncioConnection
from pika.exchange_type import ExchangeType

import asyncio, functools, json, logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
logger = logging.getLogger(__name__)


class ExamplePublisher(object):
    EXCHANGE_NAME = 'broker_exchange'
    EXCHANGE_TYPE = ExchangeType.direct
    ROUTING_KEY = 'example.text'

    def __init__(self, amqp_url, on_exchange_ok=None, on_bind_ok=None, on_message=None, on_publish_ack=None):
        self._connection = None
        self._channel = None

        self._deliveries = []
        self._acked = 0
        self._nacked = 0
        self._message_number = 0

        self._stopping = False
        self._url = amqp_url
        self._on_exchange_ok = on_exchange_ok
        self._on_bind_ok = on_bind_ok
        self._on_message = on_message
        self._on_publish_ack = on_publish_ack

    async def connect(self, delay=0):
        if delay > 0:
            logger.info(f'Waiting for {delay}s before connection attempt.')
            await asyncio.sleep(delay)

        logger.info('Connecting to %s', self._url)
        return AsyncioConnection(
            pika.URLParameters(self._url),
            on_open_callback=self.on_connection_open,
            on_open_error_callback=self.on_connection_open_error,
            on_close_callback=self.on_connection_closed)

    def on_connection_open(self, connection):
        logger.info('Connection opened')
        self._connection = connection
        self.open_channel()

    def on_connection_open_error(self, _unused_connection, err):
        logger.error('Connection open failed: %s', err)
        self._channel = None

        if not self._stopping:
            asyncio.create_task(self.connect(5))

    def on_connection_closed(self, _unused_connection, reason):
        logger.warning('Connection closed: %s', reason)
        self._channel = None

        if not self._stopping:
            asyncio.create_task(self.connect(5))

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

        logger.info(f'Declaring exchange {self.EXCHANGE_NAME}')
        self._channel.exchange_declare(
            exchange=self.EXCHANGE_NAME,
            exchange_type=self.EXCHANGE_TYPE,
            durable=True,
            callback=self.on_exchange_declareok)

    def on_channel_closed(self, channel, reason):
        logger.warning('Channel %i was closed: %s', channel, reason)
        self._channel = None

        if not (self._connection.is_closed or self._connection.is_closing):
            self.open_channel()

    def on_exchange_declareok(self, method):
        logger.info(f'Exchange declared: {method}')

        if self._on_exchange_ok is not None:
            logger.info('Calling on_exchange_ok callback.')
            self._on_exchange_ok()

    def queue_declare(self, queue_name):
        logger.info(f'Declaring queue {queue_name}')
        cb = functools.partial(self.on_queue_declareok, queue_name=queue_name)
        self._channel.queue_declare(queue=queue_name, durable=True, callback=cb)

    def on_queue_declareok(self, _unused_frame, queue_name):
        logger.info('Binding %s to %s with %s', self.EXCHANGE_NAME, queue_name, self.ROUTING_KEY)
        self._channel.queue_bind(queue_name, self.EXCHANGE_NAME, routing_key=self.ROUTING_KEY, callback=self.on_bindok)

    def on_bindok(self, _unused_frame):
        logger.info('Queue bound')
        if self._on_bind_ok is not None:
            logger.info('Calling on_bind_ok callback.')
            self._on_bind_ok()

    def start_listening(self, queue_name):
        logger.info('Adding consumer cancellation callback')
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)
        self._consumer_tag = self._channel.basic_consume(queue_name, self._on_message)

    def on_consumer_cancelled(self, method_frame):
        logger.info('Consumer was cancelled remotely, shutting down: %r', method_frame)
        if self._channel:
            self._channel.close()

    def on_delivery_confirmation(self, method_frame):
        confirmation_type = method_frame.method.NAME.split('.')[1].lower()
        logger.info('Received %s for delivery tag: %i', confirmation_type, method_frame.method.delivery_tag)
        if confirmation_type == 'ack':
            self._acked += 1
        elif confirmation_type == 'nack':
            self._nacked += 1
        self._deliveries.remove(method_frame.method.delivery_tag)

        if self._on_publish_ack is not None:
            asyncio.create_task(self._on_publish_ack(method_frame.method.delivery_tag))

        #logger.info(
        #    'Published %i messages, %i have yet to be confirmed, '
        #    '%i were acked and %i were nacked', self._message_number,
        #    len(self._deliveries), self._acked, self._nacked)

    def publish_message(self, message) -> Integral:
        if self._channel is None or not self._channel.is_open:
            return

        properties = pika.BasicProperties(
            app_id='broker',
            content_type='application/json',
            delivery_mode = pika.spec.PERSISTENT_DELIVERY_MODE
            )

        self._channel.basic_publish(self.EXCHANGE_NAME, self.ROUTING_KEY,
                                    json.dumps(message, ensure_ascii=False),
                                    properties)
        self._message_number += 1
        self._deliveries.append(self._message_number)
        logger.info('Published message # %i', self._message_number)
        return self._message_number

    def ack(self, delivery_tag: Integral) -> None:
        if self._connection.is_open and self._channel is not None:
            self._channel.basic_ack(delivery_tag)
