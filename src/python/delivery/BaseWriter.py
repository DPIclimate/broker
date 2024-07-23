from threading import Thread
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

        use_delivery_table = True

        delivery_thread = None
        try:
            dao.create_delivery_table(self.name)

            delivery_thread = Thread(target=self.delivery_thread_proc, name='delivery_thread')
            delivery_thread.start()
        except dao.DAOException as err:
            use_delivery_table = False

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
                for method, properties, body in self.channel.consume(f'{self.name}_logical_msg_queue'):
                    delivery_tag = method.delivery_tag

                    # If the finish flag is set, reject the message so RabbitMQ will re-queue it
                    # and return early.
                    if not self.keep_running:
                        lu.cid_logger.info(f'NACK delivery tag {delivery_tag}, keep_running is False', extra=msg)
                        self.channel.basic_reject(delivery_tag)
                        continue    # This will break from loop without running all the logic within the loop below here.

                    msg = json.loads(body)
                    logging.info('Adding message to delivery table')
                    dao.add_delivery_msg(self.name, msg)
                    self.channel.basic_ack(delivery_tag)

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

        # Tell the delivery thread to stop if the main thread got an error.
        self.keep_running = False
        if self.connection is not None:
            logging.info('Closing connection')
            self.connection.close()

        logging.info('Waiting for delivery thread')
        delivery_thread.join()

    def delivery_thread_proc(self) -> None:
        logging.info('Delivery threat started')
        while self.keep_running:
            count = dao.get_delivery_msg_count(self.name)
            if count < 1:
                time.sleep(30)
                continue

            logging.info(f'Processing {count} messages')
            msg_rows = dao.get_delivery_msg_batch(self.name)
            for msg_uid, msg, retry_count in msg_rows:
                logging.info(f'msg from table {msg_uid}, {retry_count}')
                if not self.keep_running:
                    break

                p_uid = msg[BrokerConstants.PHYSICAL_DEVICE_UID_KEY]
                l_uid = msg[BrokerConstants.LOGICAL_DEVICE_UID_KEY]
                lu.cid_logger.info(f'Accepted message from physical / logical device ids {p_uid} / {l_uid}', extra=msg)

                pd = dao.get_physical_device(p_uid)
                if pd is None:
                    lu.cid_logger.error(f'Could not find physical device, dropping message: {msg}', extra=msg)
                    dao.remove_delivery_msg(self.name, msg_uid)

                ld = dao.get_logical_device(l_uid)
                if ld is None:
                    lu.cid_logger.error(f'Could not find logical device, dropping message: {msg}', extra=msg)
                    dao.remove_delivery_msg(self.name, msg_uid)

                rc = self.on_message(pd, ld, msg, retry_count)
                if rc == BaseWriter.MSG_OK:
                    lu.cid_logger.info('Message processed ok.', extra=msg)
                    dao.remove_delivery_msg(self.name, msg_uid)
                elif rc == BaseWriter.MSG_RETRY:
                    # This is where the message should be published to a different exchange,
                    # private to the delivery service in question, so it can be retried later
                    # but not stuck at the head of the queue and immediately redelivered to
                    # here, possibly causing an endless loop.
                    lu.cid_logger.warning('Message processing failed, retrying message.', extra=msg)
                    dao.retry_delivery_msg(self.name, msg_uid)
                elif rc == BaseWriter.MSG_FAIL:
                    lu.cid_logger.error('Message processing failed, dropping message.', extra=msg)
                    dao.remove_delivery_msg(self.name, msg_uid)
                else:
                    logging.error(f'Invalid message processing return value: {rc}')

        dao.stop()
        logging.info('Delivery threat stopped.')

    def on_message(self, pd: PhysicalDevice, ld: LogicalDevice, msg: dict[Any], retry_count: int) -> int:
        logging.info(f'{pd.name} / {ld.name} / {retry_count}: {msg}')
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
