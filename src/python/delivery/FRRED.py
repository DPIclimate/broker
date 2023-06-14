"""
This program receives logical device timeseries messages and writes them into
the volume shared with DataBolt.

The messages are written to a file in exactly the form they are received from
the logical mapper.

Intersect wants both the physical and logical device ids.

This code expects a volume shared with the DataBolt container to be mounted and
writable at /raw_data. DataBolt expects only directories under its raw_data
directory, and then a set of files with each of those directories. Each
directory is processed as a batch and a completion file written when the
batch has been successfully processed.
"""

import dateutil.parser

import json, logging, math, os, signal, sys, time, uuid

import BrokerConstants

import pika, pika.channel, pika.spec
from pika.exchange_type import ExchangeType

import api.client.Ubidots as ubidots

import api.client.DAO as dao
import util.LoggingUtil as lu

_user = os.environ['RABBITMQ_DEFAULT_USER']
_passwd = os.environ['RABBITMQ_DEFAULT_PASS']
_host = os.environ['RABBITMQ_HOST']
_port = os.environ['RABBITMQ_PORT']

_amqp_url_str = f'amqp://{_user}:{_passwd}@{_host}:{_port}/%2F'

_channel = None

_finish = False

_q_name = 'databolt_delivery'

_raw_data_name = '/raw_data'


def sigterm_handler(sig_no, stack_frame) -> None:
    """
    Handle SIGTERM from docker by closing the mq and db connections and setting a
    flag to tell the main loop to exit.
    """
    global _finish, _channel

    logging.info(f'{signal.strsignal(sig_no)}, setting finish to True')
    _finish = True
    dao.stop()

    # This breaks the endless loop in main.
    _channel.cancel()


def main():
    """
    Initiate the connection to RabbitMQ and then idle until asked to stop.

    Because the messages from RabbitMQ arrive via async processing this function
    has nothing to do after starting connection.

    It would be good to find a better way to do nothing than the current loop.
    """
    global _channel, _finish, _q_name

    logging.info('===============================================================')
    logging.info('               STARTING FRRED DATABOLT WRITER')
    logging.info('===============================================================')

    logging.info('Opening connection')
    connection = None
    conn_attempts = 0
    backoff = 10
    while connection is None:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(_amqp_url_str))
        except:
            conn_attempts += 1
            logging.warning(f'Connection to RabbitMQ attempt {conn_attempts} failed.')

            if conn_attempts % 5 == 0 and backoff < 60:
                backoff += 10

            time.sleep(backoff)

    logging.info('Opening channel')
    _channel = connection.channel()
    _channel.basic_qos(prefetch_count=1)
    logging.info('Declaring exchange')
    _channel.exchange_declare(
            exchange=BrokerConstants.LOGICAL_TIMESERIES_EXCHANGE_NAME,
            exchange_type=ExchangeType.fanout,
            durable=True)
    logging.info('Declaring queue')
    _channel.queue_declare(queue=_q_name, durable=True)
    logging.info('Binding queue to exchange')
    _channel.queue_bind(_q_name, BrokerConstants.LOGICAL_TIMESERIES_EXCHANGE_NAME, 'logical_timeseries')

    # This loops until _channel.cancel is called in the signal handler.
    for method, properties, body in _channel.consume(_q_name):
        on_message(_channel, method, properties, body)

    logging.info('Closing connection')
    connection.close()


def on_message(channel, method, properties, body):
    """
    This function is called when a message arrives from RabbitMQ.
    """

    global _channel, _finish

    delivery_tag = method.delivery_tag

    # If the finish flag is set, reject the message so RabbitMQ will re-queue it
    # and return early.
    if _finish:
        lu.cid_logger.info(f'NACK delivery tag {delivery_tag}, _finish is True', extra=msg)
        _channel.basic_reject(delivery_tag)
        return

    try:
        # Parse the message just to confirm it is valid JSON.
        msg = json.loads(body)
        p_uid = msg[BrokerConstants.PHYSICAL_DEVICE_UID_KEY]
        l_uid = msg[BrokerConstants.LOGICAL_DEVICE_UID_KEY]

        # TODO: Look into routing keys for deciding which messages to pass on to Intersect.

        # Only messages from Wombat nodes should be processed. This is a bit coarse-grained
        # because Wombats could conceivably be used for other projects, but that is very
        # unlikely now. To deterimine if the message is from a Wombat, look up the physical
        # device and check the source_name.
        pd = dao.get_physical_device(p_uid)
        if pd is None:
            lu.cid_logger.error(f'Physical device not found, cannot continue. Dropping message.', extra=msg)
            # Ack the message, even though we cannot process it. We don't want it redelivered.
            # We can change this to a Nack if that would provide extra context somewhere.
            _channel.basic_ack(delivery_tag)
            return

        if BrokerConstants.WOMBAT != pd.source_name:
            _channel.basic_ack(delivery_tag)
            return

        lu.cid_logger.info(f'Physical device: {pd.name}', extra=msg)

        # May as well use the message context id for the DataBolt directory and file name.
        if not os.path.isdir(_raw_data_name):
            logging.error(f'DataBolt {_raw_data_name} directory not found. This should be a mounted volume shared with the DataBolt container.')
            sys.exit(1)

        msg_uuid = msg[BrokerConstants.CORRELATION_ID_KEY]

        old_umask = os.umask(0)
        try:
            lu.cid_logger.info(json.dumps(msg), extra=msg)
            os.mkdir(f'{_raw_data_name}/{msg_uuid}')
            with open(f'{_raw_data_name}/{msg_uuid}/{msg_uuid}.json', 'w') as f:
                # The body argument is bytes, not a string. Using json.dump is a
                # simple way to get a string written to the file.
                json.dump(msg, f)

        except:
            logging.exception('Failed to write message to DataBolt directory.')
            _channel.basic_ack(delivery_tag)
            sys.exit(1)

        os.umask(old_umask)

        # This tells RabbitMQ the message is handled and can be deleted from the queue.    
        _channel.basic_ack(delivery_tag)

    except BaseException:
        logging.exception('Error while processing message.')
        _channel.basic_reject(delivery_tag, requeue=False)


if __name__ == '__main__':
    if not os.path.isdir(_raw_data_name):
        logging.error(f'DataBolt {_raw_data_name} directory not found. This should be a mounted volume shared with the DataBolt container.')
        sys.exit(1)

    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Does not return until SIGTERM is received.
    main()
    logging.info('Exiting.')
