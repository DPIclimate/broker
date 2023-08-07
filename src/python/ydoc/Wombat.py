import datetime, dateutil.parser

import asyncio, json, logging, re, signal, sys, uuid
from typing import Dict, Optional

import BrokerConstants
from pdmodels.Models import PhysicalDevice
from pika.exchange_type import ExchangeType

import api.client.RabbitMQ as mq
import api.client.TTNAPI as ttn

import api.client.DAO as dao

import util.LoggingUtil as lu
import util.Timestamps as ts

# Prometheus metrics
from prometheus_client import Counter, start_http_server

# Prometheus metrics
listener_starts_counter = Counter('wombat_listener_starts', 'Number of times the Wombat listener has started')
graceful_exit_counter = Counter('wombat_graceful_exits', 'Number of times the application has gracefully exited')
messages_received_counter = Counter('wombat_messages_received', 'Number of messages received from RabbitMQ')
messages_acknowledged_counter = Counter('wombat_messages_acknowledged', 'Number of messages acknowledged to RabbitMQ')
messages_published_counter = Counter('wombat_messages_published', 'Number of messages published to RabbitMQ')
devices_created_counter = Counter('wombat_devices_created', 'Number of physical devices created in the database')
devices_updated_counter = Counter('wombat_devices_updated', 'Number of physical devices updated in the database')
exceptions_caught_counter = Counter('wombat_exceptions_caught', 'Number of exceptions caught during processing')
message_processing_errors_counter = Counter('wombat_message_processing_errors', 'Number of errors while processing messages')
# Start up the server to expose the metrics.
start_http_server(8004)

std_logger = logging.getLogger(__name__)

rx_channel: mq.RxChannel = None
tx_channel: mq.TxChannel = None
mq_client: mq.RabbitMQConnection = None
finish = False

def sigterm_handler(sig_no, stack_frame) -> None:
    """
    Handle SIGTERM from docker by closing the mq and db connections and setting a
    flag to tell the main loop to exit.
    """
    global finish, mq_client

    logging.debug(f'{signal.strsignal(sig_no)}, setting finish to True')
    finish = True
    dao.stop()
    mq_client.stop()


async def main():
    """
    Initiate the connection to RabbitMQ and then idle until asked to stop.

    Because the messages from RabbitMQ arrive via async processing this function
    has nothing to do after starting connection.

    It would be good to find a better way to do nothing than the current loop.
    """
    global mq_client, rx_channel, tx_channel, finish
    listener_starts_counter.inc()
    logging.info('===============================================================')
    logging.info('               STARTING Wombat LISTENER')
    logging.info('===============================================================')

    # The default MQTT topic of YDOC devices is YDOC/<serial#> which RabbitMQ converts into a routing key of YDOC.<serial#>.
    # It seems we can use the MQTT topic wildcard of # to get all YDOC messages.
    rx_channel = mq.RxChannel('amq.topic', exchange_type=ExchangeType.topic, queue_name='wombat_listener', on_message=on_message, routing_key='wombat')
    tx_channel = mq.TxChannel(exchange_name=BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME, exchange_type=ExchangeType.fanout)
    mq_client = mq.RabbitMQConnection(channels=[rx_channel, tx_channel])
    asyncio.create_task(mq_client.connect())

    #while not (rx_channel.is_open and tx_channel.is_open):
    while not (rx_channel.is_open):
        await asyncio.sleep(0)

    while not finish:
        await asyncio.sleep(2)

    while not mq_client.stopped:
        await asyncio.sleep(1)


def on_message(channel, method, properties, body):
    messages_received_counter.inc()
    """
    This function is called when a message arrives from RabbitMQ.
    """
    global rx_channel, tx_channel, finish

    delivery_tag = method.delivery_tag

    # If the finish flag is set, reject the message so RabbitMQ will re-queue it
    # and return early.
    if finish:
        rx_channel._channel.basic_reject(delivery_tag)
        return

    try:
        correlation_id = str(uuid.uuid4())
        lu.cid_logger.info(f'Message as received: {body}', extra={BrokerConstants.CORRELATION_ID_KEY: correlation_id})

        msg = {}
        try:
            msg = json.loads(body)
        except Exception as e:
            std_logger.info(f'JSON parsing failed, ignoring message')
            rx_channel._channel.basic_ack(delivery_tag)
            return

        # This code could put the cid into msg (and does so later) and pass msg into the lu_cid
        # logger calls. However, for consistency with other modules and to avoid problems if this code
        # is ever copy/pasted somewhere we will stick with building a msg_with_cid object and using
        # that for logging.
        msg_with_cid = {BrokerConstants.CORRELATION_ID_KEY: correlation_id, BrokerConstants.RAW_MESSAGE_KEY: msg}

        # Record the message to the all messages table before doing anything else to ensure it
        # is saved. Attempts to add duplicate messages are ignored in the DAO.
        msg_ts = dateutil.parser.isoparse(msg[BrokerConstants.TIMESTAMP_KEY])
        dao.add_raw_json_message(BrokerConstants.WOMBAT, msg_ts, correlation_id, msg)

        source_ids = msg['source_ids']
        serial_no = source_ids['serial_no']
        lu.cid_logger.info(f'Accepted message from {serial_no}', extra=msg_with_cid)

        pds = dao.get_pyhsical_devices_using_source_ids(BrokerConstants.WOMBAT, source_ids)
        if len(pds) < 1:
            lu.cid_logger.info(f'Message from a new device.', extra=msg_with_cid)
            lu.cid_logger.info(body, extra=msg_with_cid)

            lu.cid_logger.info('Device not found, creating physical device.', extra=msg_with_cid)

            props = {
                BrokerConstants.CREATION_CORRELATION_ID_KEY: correlation_id,
                BrokerConstants.LAST_MSG: msg
            }

            device_name = f'Wombat-{serial_no}'
            pd = PhysicalDevice(source_name=BrokerConstants.WOMBAT, name=device_name, location=None, last_seen=msg_ts, source_ids=source_ids, properties=props)
            pd = dao.create_physical_device(pd)
            devices_created_counter.inc()
        else:
            pd = pds[0]
            pd.last_seen = msg_ts
            pd.properties[BrokerConstants.LAST_MSG] = msg
            pd = dao.update_physical_device(pd)
            devices_updated_counter.inc()

        if pd is None:
            message_processing_errors_counter.inc()
            lu.cid_logger.error(f'Physical device not found, message processing ends now. {correlation_id}', extra=msg_with_cid)
            rx_channel._channel.basic_ack(delivery_tag)
            return

        msg[BrokerConstants.CORRELATION_ID_KEY] = correlation_id
        msg[BrokerConstants.PHYSICAL_DEVICE_UID_KEY] = pd.uid

        lu.cid_logger.debug(f'Publishing message: {msg}', extra=msg_with_cid)
        tx_channel.publish_message('physical_timeseries', msg)
        messages_published_counter.inc()

        # This tells RabbitMQ the message is handled and can be deleted from the queue.
        rx_channel._channel.basic_ack(delivery_tag)
        messages_acknowledged_counter.inc()
        lu.cid_logger.debug('Acking message from ttn_raw.', extra=msg_with_cid)
    except Exception as e:
        exceptions_caught_counter.inc()
        std_logger.exception('Error while processing message.')
        rx_channel._channel.basic_ack(delivery_tag)


if __name__ == '__main__':
    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Does not return until SIGTERM is received.
    asyncio.run(main())
    logging.info('Exiting.')
    graceful_exit_counter.inc()