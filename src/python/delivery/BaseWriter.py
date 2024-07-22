from typing import Any

from pdmodels.Models import LogicalDevice, PhysicalDevice

import json, logging, os, signal, time

import BrokerConstants

import pika, pika.channel, pika.spec
from pika.exchange_type import ExchangeType

import api.client.DAO as dao
import util.LoggingUtil as lu

_user = os.environ['RABBITMQ_DEFAULT_USER']
_passwd = os.environ['RABBITMQ_DEFAULT_PASS']
_host = os.environ['RABBITMQ_HOST']
_port = os.environ['RABBITMQ_PORT']

_amqp_url_str = f'amqp://{_user}:{_passwd}@{_host}:{_port}/%2F'


class BaseWriter:
    MSG_OK = 0
    MSG_RETRY = 1
    MSG_FAIL = 2

    def __init__(self, name) -> None:
        #super().__init__()
        self.name: str = name
        self.connection = None
        self.channel = None
        self.keep_running = True
        signal.signal(signal.SIGTERM, self.sigterm_handler)

    def run(self) -> None:
        logging.info('===============================================================')
        logging.info(f'               STARTING {self.name.upper()} WRITER')
        logging.info('===============================================================')

        while self.keep_running:
            try:
                logging.info('Opening connection')
                self.connection = None
                connection = pika.BlockingConnection(pika.URLParameters(_amqp_url_str))

                logging.info('Opening channel')
                self.channel = connection.channel()
                self.channel.basic_qos(prefetch_count=1)
                logging.info('Declaring exchange')
                self.channel.exchange_declare(
                        exchange=BrokerConstants.LOGICAL_TIMESERIES_EXCHANGE_NAME,
                        exchange_type=ExchangeType.fanout,
                        durable=True)
                logging.info('Declaring queue')
                self.channel.queue_declare(queue=f'{self.name}_logical_msg_queue', durable=True)
                self.channel.queue_bind(f'{self.name}_logical_msg_queue', BrokerConstants.LOGICAL_TIMESERIES_EXCHANGE_NAME, 'logical_timeseries')

                logging.info('Waiting for messages.')
                # This loops until _channel.cancel is called in the signal handler.
                for method, properties, body in self.channel.consume('ubidots_logical_msg_queue'):
                    delivery_tag = method.delivery_tag
                    logging.info(method)
                    logging.info(properties)

                    # If the finish flag is set, reject the message so RabbitMQ will re-queue it
                    # and return early.
                    if not self.keep_running:
                        lu.cid_logger.info(f'NACK delivery tag {delivery_tag}, keep_running is False', extra=msg)
                        self.channel.basic_reject(delivery_tag)
                        continue    # This will break from loop without running all the logic within the loop below here.

                    msg = json.loads(body)
                    p_uid = msg[BrokerConstants.PHYSICAL_DEVICE_UID_KEY]
                    l_uid = msg[BrokerConstants.LOGICAL_DEVICE_UID_KEY]
                    lu.cid_logger.info(f'Accepted message from physical / logical device ids {p_uid} / {l_uid}', extra=msg)

                    pd = dao.get_physical_device(p_uid)
                    if pd is None:
                        lu.cid_logger.error(f'Could not find physical device, dropping message: {body}', extra=msg)
                        return BaseWriter.MSG_FAIL

                    ld = dao.get_logical_device(l_uid)
                    if ld is None:
                        lu.cid_logger.error(f'Could not find logical device, dropping message: {body}', extra=msg)
                        return BaseWriter.MSG_FAIL

                    rc = self.on_message(pd, ld, msg)
                    if rc == BaseWriter.MSG_OK:
                        lu.cid_logger.info('Message processed ok.', extra=msg)
                        self.channel.basic_ack(delivery_tag)
                    elif rc == BaseWriter.MSG_RETRY:
                        # This is where the message should be published to a different exchange,
                        # private to the delivery service in question, so it can be retried later
                        # but not stuck at the head of the queue and immediately redelivered to
                        # here, possibly causing an endless loop.
                        lu.cid_logger.warning('Message processing failed, retrying message.', extra=msg)
                        self.channel.basic_nack(delivery_tag, requeue=True)
                    elif rc == BaseWriter.MSG_FAIL:
                        lu.cid_logger.error('Message processing failed, dropping message.', extra=msg)
                        self.channel.basic_nack(delivery_tag, requeue=False)
                    else:
                        logging.error(f'Invalid message processing return value: {rc}')

            except pika.exceptions.ConnectionClosedByBroker:
                    logging.info('Connection closed by server.')
                    break

            except pika.exceptions.AMQPChannelError as err:
                logging.exception(err)
                break

            except pika.exceptions.AMQPConnectionError:
                logging.exception(err)
                logging.warning('Connection was closed, retrying after a pause.')
                time.sleep(10)
                continue

        if self.connection is not None:
            logging.info('Closing connection')
            self.connection.close()

        logging.info('Waiting forever')
        while True:
            time.sleep(60)

    def on_message(self, pd: PhysicalDevice, ld: LogicalDevice, msg: dict[Any]) -> int:
        logging.info(f'{pd.name} / {ld.name}: {msg}')
        return BaseWriter.MSG_OK

    def sigterm_handler(self, sig_no, stack_frame) -> None:
        """
        Handle SIGTERM from docker by closing the mq and db connections and setting a
        flag to tell the main loop to exit.
        """
        logging.info(f'{signal.strsignal(sig_no)}, setting keep_running to False')
        self.keep_running = False
        dao.stop()

        # This breaks the endless loop in main.
        self.channel.cancel()


if __name__ == '__main__':
    # Does not return until SIGTERM is received.
    deliverer = BaseWriter('test')
    deliverer.run()

    logging.info('Exiting')
