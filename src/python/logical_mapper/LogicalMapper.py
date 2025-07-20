"""
The logical mapper receives messages from the physical_timeseries queue
and determines which logical device they should be sent to.

If no logical device is mapped to the physical device, a new logical device
is created.

The message has the logical device id added to it and published to the
logical_timeseries queue where it can be picked up by delivery services.

It is up to the delivery services to decide what to do when they receive
a message for a newly created logical device.

For example, delivery services for IoT platforms such as ThingsBoard or
Ubidots should create corresponding devices in those services and add
information to the logical device properties object allowing the logical
device to be associated with the IoT platform device.
"""

import asyncio, json, logging, signal
import datetime

import dateutil.parser

import BrokerConstants
from pika.exchange_type import ExchangeType
import api.client.RabbitMQ as mq
import api.client.DAO as dao
import util.LoggingUtil as lu

_rx_channel = None
_tx_channel = None
_mq_client = None
_finish = False

_max_delta = datetime.timedelta(hours=-1)


def sigterm_handler(sig_no, stack_frame) -> None:
    """
    Handle SIGTERM from docker by closing the mq and db connections and setting a
    flag to tell the main loop to exit.
    """
    global _finish, _mq_client

    logging.info(f'{signal.strsignal(sig_no)}, setting _finish to True')
    _finish = True
    dao.stop()
    _mq_client.stop()


async def main():
    """
    Initiate the connection to RabbitMQ and then idle until asked to stop.

    Because the messages from RabbitMQ arrive via async processing this function
    has nothing to do after starting connection.

    It would be good to find a better way to do nothing than the current loop.
    """
    global _mq_client, _rx_channel, _tx_channel, _finish

    logging.info('===============================================================')
    logging.info('               STARTING LOGICAL MAPPER')
    logging.info('===============================================================')

    _rx_channel = mq.RxChannel(exchange_name=BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME, exchange_type=ExchangeType.fanout, queue_name='lm_physical_timeseries', on_message=on_message)
    _tx_channel = mq.TxChannel(exchange_name=BrokerConstants.LOGICAL_TIMESERIES_EXCHANGE_NAME, exchange_type=ExchangeType.fanout)
    _mq_client = mq.RabbitMQConnection(channels=[_rx_channel, _tx_channel])

    asyncio.create_task(_mq_client.connect())

    while not (_rx_channel.is_open and _tx_channel.is_open):
        await asyncio.sleep(0)

    while not _finish:
        await asyncio.sleep(2)

    while not _mq_client.stopped:
        await asyncio.sleep(1)


def on_message(channel, method, properties, body):
    """
    This function is called when a message arrives from RabbitMQ.
    """

    global _rx_channel, _tx_channel, _finish

    delivery_tag = method.delivery_tag

    # If the _finish flag is set, reject the message so RabbitMQ will re-queue it
    # and return early.
    if _finish:
        _rx_channel._channel.basic_reject(delivery_tag)
        return

    try:
        msg = json.loads(body)

        p_uid = msg[BrokerConstants.PHYSICAL_DEVICE_UID_KEY]
        pd = dao.get_physical_device(p_uid)
        if pd is None:
            lu.cid_logger.error(f'Physical device not found, cannot continue. Dropping message.', extra=msg)
            # Ack the message, even though we cannot process it. We don't want it redelivered.
            # We can change this to a Nack if that would provide extra context somewhere.
            _rx_channel._channel.basic_ack(delivery_tag)
            return

        lu.cid_logger.info(f'Accepted message from {pd.name}', extra=msg)

        ts_str = msg[BrokerConstants.TIMESTAMP_KEY]
        ts = dateutil.parser.isoparse(ts_str)

        mapping = dao.get_physical_mapping_at_timestamp(p_uid, ts)
        if mapping is None or mapping.is_active is not True:
            # Add the message even though it has no logical device id in it.
            dao.insert_physical_timeseries_message(msg)

            if mapping is None:
                lu.cid_logger.warning(f'No device mapping found for {pd.source_ids}, cannot continue. Dropping message.', extra=msg)
            else:
                lu.cid_logger.warning(f'Mapping for {pd.source_ids} is paused, cannot continue. Dropping message.', extra=msg)

            # Ack the message, even though we cannot process it. We don't want it redelivered.
            # We can change this to a Nack if that would provide extra context somewhere.
            _rx_channel._channel.basic_ack(delivery_tag)
            return

        msg[BrokerConstants.LOGICAL_DEVICE_UID_KEY] = mapping.ld.uid

        dao.insert_physical_timeseries_message(msg)

        ld = mapping.ld

        # Determine if the message has a future timestamp.
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        ts_delta = utc_now - ts

        # Drop messages with a timestamp more than 1 hour in the future.
        if ts_delta < _max_delta:
            lu.cid_logger.warning(f'Message with future timestamp. Dropping message.', extra=msg)
            # Ack the message, even though we cannot process it. We don't want it redelivered.
            # We can change this to a Nack if that would provide extra context somewhere.
            _rx_channel._channel.basic_ack(delivery_tag)
            return

        if ts > utc_now:
            # If the timestamp is a bit in the future then make the last seen time 'now'.
            ld.last_seen = utc_now
        else:
            ld.last_seen = ts

        lu.cid_logger.info(f'Timestamp from message for LD last seen update: {ld.last_seen}', extra=msg)
        ld.properties[BrokerConstants.LAST_MSG] = msg
        dao.update_logical_device(ld)

        _tx_channel.publish_message('logical_timeseries', msg)

        # This tells RabbitMQ the message is handled and can be deleted from the queue.
        _rx_channel._channel.basic_ack(delivery_tag)

    except BaseException as e:
        logging.exception('Error while processing message')
        _rx_channel._channel.basic_ack(delivery_tag)


if __name__ == '__main__':
    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Does not return until SIGTERM is received.
    asyncio.run(main())
    logging.info('Exiting.')
