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

        # Find the device using only the serial_no.
        find_source_id = {'serial_no': serial_no}
        pds = dao.get_pyhsical_devices_using_source_ids(BrokerConstants.WOMBAT, find_source_id)
        if len(pds) < 1:
            lu.cid_logger.info('Device not found, creating physical device.', extra=msg_with_cid)

            props = {
                BrokerConstants.CREATION_CORRELATION_ID_KEY: correlation_id,
                BrokerConstants.LAST_MSG: msg
            }

            device_name = f'Wombat-{serial_no}'
            pd = PhysicalDevice(source_name=BrokerConstants.WOMBAT, name=device_name, location=None, last_seen=msg_ts, source_ids=source_ids, properties=props)
            pd = dao.create_physical_device(pd)
        else:
            pd = pds[0]
            # Update the source_ids because the Wombat firmware was updated to include the SDI-12 sensor
            # IDs in the source_ids object after physical devices with only the serial_no had been created.
            # Additionally, something like an AWS might get replaced so there will be a new SDI-12 ID for that.
            pd.source_ids = source_ids
            pd.last_seen = msg_ts
            pd.properties[BrokerConstants.LAST_MSG] = msg
            pd = dao.update_physical_device(pd)

        if pd is None:
            lu.cid_logger.error(f'Physical device not found, message processing ends now. {correlation_id}', extra=msg_with_cid)
            rx_channel._channel.basic_ack(delivery_tag)
            return

        lu.cid_logger.info(f'Using device id {pd.uid}', extra=msg_with_cid)

        msg[BrokerConstants.CORRELATION_ID_KEY] = correlation_id
        msg[BrokerConstants.PHYSICAL_DEVICE_UID_KEY] = pd.uid

        tx_channel.publish_message('physical_timeseries', msg)

        # This tells RabbitMQ the message is handled and can be deleted from the queue.
        rx_channel._channel.basic_ack(delivery_tag)
    except Exception as e:
        std_logger.exception('Error while processing message.')
        rx_channel._channel.basic_ack(delivery_tag)


if __name__ == '__main__':
    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Does not return until SIGTERM is received.
    asyncio.run(main())
    logging.info('Exiting.')
