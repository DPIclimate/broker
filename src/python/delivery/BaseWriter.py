from threading import Thread, Event
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
        self.name: str = name
        self.connection = None
        self.channel = None
        self.keep_running = True

        # The Event is used to signal the delivery thread that a new message has arrived or
        # that it should stop.
        self.evt = Event()

        signal.signal(signal.SIGTERM, self.sigterm_handler)

    def run(self) -> None:
        """
        This method runs the blocking MQTT loop, waiting for messages from upstream
        and writing them to the backing table. A separate thread reads them from
        the backing table and attempts to deliver them.
        """
        logging.info('===============================================================')
        logging.info(f'               STARTING {self.name.upper()} WRITER')
        logging.info('===============================================================')

        delivery_thread = None
        try:
            dao.create_delivery_table(self.name)

            self.evt.clear()
            delivery_thread = Thread(target=self.delivery_thread_proc, name='delivery_thread')
            delivery_thread.start()
        except dao.DAOException as err:
            logging.exception('Failed to find or create service table')
            exit(1)

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
                    delivery_tag = None
                    if method is not None:
                        delivery_tag = method.delivery_tag

                    # If the finish flag is set, reject the message so RabbitMQ will re-queue it
                    # and return early.
                    if not self.keep_running:
                        if delivery_tag is not None:
                            lu.cid_logger.info(f'NACK delivery tag {delivery_tag}, keep_running is False', extra=msg)
                            self.channel.basic_reject(delivery_tag)
                        self.channel.cancel();
                        break

                    msg = json.loads(body)
                    lu.cid_logger.info('Adding message to delivery table', extra=msg)
                    dao.add_delivery_msg(self.name, msg)
                    self.channel.basic_ack(delivery_tag)
                    self.evt.set()

            except pika.exceptions.ConnectionClosedByBroker:
                logging.info('Connection closed by server.')
                break

            except pika.exceptions.AMQPChannelError as err:
                logging.exception(err)
                break

            except pika.exceptions.AMQPConnectionError as err:
                logging.exception(err)
                logging.warning('Connection was closed, retrying after a pause.')
                time.sleep(10)

        # Tell the delivery thread to stop if the main thread got an error.
        self.keep_running = False
        self.evt.set()
        if self.connection is not None:
            logging.info('Closing connection')
            self.connection.close()

        logging.info('Waiting for delivery thread')
        delivery_thread.join()

    def delivery_thread_proc(self) -> None:
        """
        This method runs in a separate thread and reads messages from the backing table,
        calling the on_message handler for each one. It also removes messages from the
        backing table when on_message returns MSG_OK or MSG_FAIL, and maintains the retry_count
        attribute on MSG_RETRY returns.
        """
        logging.info('Delivery thread started')
        while self.keep_running:
            count = dao.get_delivery_msg_count(self.name)
            if count < 1:
                self.evt.wait()
                self.evt.clear()

                if not self.keep_running:
                    break

                count = dao.get_delivery_msg_count(self.name)
                if count < 1:
                    continue

            if not self.keep_running:
                break

            logging.info(f'Processing {count} messages')
            msg_rows = dao.get_delivery_msg_batch(self.name)
            for msg_uid, msg, retry_count in msg_rows:
                lu.cid_logger.info(f'msg from table {msg_uid}, retries {retry_count}', extra=msg)
                if not self.keep_running:
                    break

                if BrokerConstants.PHYSICAL_DEVICE_UID_KEY not in msg:
                    lu.cid_logger.info(f'No physical device id, dropping message: {msg}', extra=msg)
                    dao.remove_delivery_msg(self.name, msg_uid)
                    continue

                p_uid = msg[BrokerConstants.PHYSICAL_DEVICE_UID_KEY]

                if BrokerConstants.LOGICAL_DEVICE_UID_KEY not in msg:
                    lu.cid_logger.info(f'No logical device id, dropping message: {msg}', extra=msg)
                    dao.remove_delivery_msg(self.name, msg_uid)
                    continue

                l_uid = msg[BrokerConstants.LOGICAL_DEVICE_UID_KEY]

                lu.cid_logger.info(f'Accepted message from physical / logical device ids {p_uid} / {l_uid}', extra=msg)

                pd = dao.get_physical_device(p_uid)
                if pd is None:
                    lu.cid_logger.error(f'Could not find physical device, dropping message: {msg}', extra=msg)
                    dao.remove_delivery_msg(self.name, msg_uid)
                    continue

                ld = dao.get_logical_device(l_uid)
                if ld is None:
                    lu.cid_logger.error(f'Could not find logical device, dropping message: {msg}', extra=msg)
                    dao.remove_delivery_msg(self.name, msg_uid)
                    continue

                lu.cid_logger.info(f'{pd.name} / {ld.name}', extra=msg)

                rc = self.on_message(pd, ld, msg, retry_count)
                if rc == BaseWriter.MSG_OK:
                    lu.cid_logger.info('Message processed ok.', extra=msg)
                    dao.remove_delivery_msg(self.name, msg_uid)
                elif rc == BaseWriter.MSG_RETRY:
                    # This is where the message should be published to a different exchange,
                    # private to the delivery service in question, so it can be retried later
                    # but not stuck at the head of the queue and immediately redelivered to
                    # here, possibly causing an endless loop.
                    #
                    # Alternatively, the retry count can be used to initially select new messages, then
                    # messages that have failed at least once.
                    lu.cid_logger.warning('Message processing failed, retrying message.', extra=msg)
                    dao.retry_delivery_msg(self.name, msg_uid)
                elif rc == BaseWriter.MSG_FAIL:
                    lu.cid_logger.error('Message processing failed, dropping message.', extra=msg)
                    dao.remove_delivery_msg(self.name, msg_uid)
                else:
                    lu.cid_logger.error(f'Invalid message processing return value: {rc}', extra=msg)

        dao.stop()
        logging.info('Delivery thread stopped.')

    def on_message(self, pd: PhysicalDevice, ld: LogicalDevice, msg: dict[Any], retry_count: int) -> int:
        """
        Subclasses must override this method and perform all transformation and delivery during
        its execution.

        Implementations must decide what constitutes a temporary failure that can be retried, how
        many times it is reasonable to retry, and when a message is undeliverable.

        pd: The PhysicalDevice that sent the message.
        ld: The LogicalDevice to deliver the message to.
        msg: The message content, in IoTa format.
        retry_count: How many times this method has returned MSG_RETRY so far.

        return BaseWriter.MSG_OK to signal the message has been delivered and can be removed from the backing table.
               BaseWriter.MSG_RETRY to signal a temporary delivery failure which is retryable.
               BaseWriter.MSG_FAIL to signal the message cannot be delivered, or has failed too many times.
        """
        lu.cid_logger.info(f'{pd.name} / {ld.name} / {retry_count}: {msg}', extra=msg)
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
