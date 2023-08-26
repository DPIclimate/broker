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

import BrokerConstants
from pika.exchange_type import ExchangeType
import api.client.RabbitMQ as mq
import api.client.DAO as dao
import util.LoggingUtil as lu

# Prometheus metrics
from prometheus_client import Counter, start_http_server
messages_received_counter = Counter('logicalmapper_messages_received', 'Number of messages received for processing')
messages_published_counter = Counter('logicalmapper_messages_published', 'Number of messages published to logical_timeseries queue')
messages_acknowledged_counter = Counter('logicalmapper_messages_acknowledged', 'Number of messages acknowledged to RabbitMQ')
messages_stored_counter = Counter('logicalmapper_messages_stored', 'Number of messages stored in the physical_timeseries table')
logical_devices_updated_counter = Counter('logicalmapper_logical_devices_updated', 'Number of logical devices updated in the database')
message_processing_errors_counter = Counter('logicalmapper_message_processing_errors', 'Number of errors during message processing')
no_device_mapping_counter = Counter('logicalmapper_no_device_mapping', 'Number of messages processed without an existing device mapping')
logical_mapper_starts_counter = Counter('logicalmapper_starts', 'Number of times the logical mapper script has started')
logical_mapper_exits_counter = Counter('logicalmapper_exits', 'Number of times the logical mapper script has exited')

# Start up the server to expose the metrics.
start_http_server(8000)

rx_channel = None
tx_channel = None
mq_client = None
finish = False


def sigterm_handler(sig_no, stack_frame) -> None:
    """
    Handle SIGTERM from docker by closing the mq and db connections and setting a
    flag to tell the main loop to exit.
    """
    global finish, mq_client

    logging.info(f'{signal.strsignal(sig_no)}, setting finish to True')
    finish = True
    dao.stop()
    mq_client.stop()


async def main():
    logical_mapper_starts_counter.inc()
    """
    Initiate the connection to RabbitMQ and then idle until asked to stop.

    Because the messages from RabbitMQ arrive via async processing this function
    has nothing to do after starting connection.

    It would be good to find a better way to do nothing than the current loop.
    """
    global mq_client, rx_channel, tx_channel, finish

    logging.info('===============================================================')
    logging.info('               STARTING LOGICAL MAPPER')
    logging.info('===============================================================')

    rx_channel = mq.RxChannel(exchange_name=BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME, exchange_type=ExchangeType.fanout, queue_name='lm_physical_timeseries', on_message=on_message)
    tx_channel = mq.TxChannel(exchange_name=BrokerConstants.LOGICAL_TIMESERIES_EXCHANGE_NAME, exchange_type=ExchangeType.fanout)
    mq_client = mq.RabbitMQConnection(channels=[rx_channel, tx_channel])

    asyncio.create_task(mq_client.connect())

    while not (rx_channel.is_open and tx_channel.is_open):
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
        msg = json.loads(body)

        p_uid = msg[BrokerConstants.PHYSICAL_DEVICE_UID_KEY]
        pd = dao.get_physical_device(p_uid)
        if pd is None:
            lu.cid_logger.error(f'Physical device not found, cannot continue. Dropping message.', extra=msg)
            # Ack the message, even though we cannot process it. We don't want it redelivered.
            # We can change this to a Nack if that would provide extra context somewhere.
            rx_channel._channel.basic_ack(delivery_tag)
            messages_acknowledged_counter.inc()
            return

        lu.cid_logger.info(f'Accepted message from {pd.name}', extra=msg)
        messages_received_counter.inc()
        # Store message in the physical timeseries table in the brokers processed, standardised msg format.
        dao.insert_physical_timeseries_message(pd.uid, msg[BrokerConstants.TIMESTAMP_KEY], msg)
        messages_stored_counter.inc()

        mapping = dao.get_current_device_mapping(p_uid)
        if mapping is None:
            no_device_mapping_counter.inc()
            lu.cid_logger.warning(f'No device mapping found for {pd.source_ids}, cannot continue. Dropping message.', extra=msg)
            # Ack the message, even though we cannot process it. We don't want it redelivered.
            # We can change this to a Nack if that would provide extra context somewhere.
            rx_channel._channel.basic_ack(delivery_tag)
            return

        msg[BrokerConstants.LOGICAL_DEVICE_UID_KEY] = mapping.ld.uid
        
        ld = mapping.ld
        ld.last_seen = msg[BrokerConstants.TIMESTAMP_KEY]
        lu.cid_logger.info(f'Timestamp from message for LD last seen update: {ld.last_seen}', extra=msg)
        ld.properties[BrokerConstants.LAST_MSG] = msg
        dao.update_logical_device(ld)
        logical_devices_updated_counter.inc()

        tx_channel.publish_message('logical_timeseries', msg)
        messages_published_counter.inc()
        # This tells RabbitMQ the message is handled and can be deleted from the queue.
        rx_channel._channel.basic_ack(delivery_tag)

    except BaseException as e:
        message_processing_errors_counter.inc()
        logging.exception('Error while processing message')
        rx_channel._channel.basic_ack(delivery_tag)


if __name__ == '__main__':
    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Does not return until SIGTERM is received.
    asyncio.run(main())
    logging.info('Exiting.')
    logical_mapper_exits_counter.inc()