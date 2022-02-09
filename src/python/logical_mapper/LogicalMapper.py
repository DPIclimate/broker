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

import asyncio, datetime, json, logging, signal

import BrokerConstants
from pdmodels.Models import LogicalDevice, PhysicalToLogicalMapping
import api.client.RabbitMQ as mq
import db.DAO as dao

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
logger = logging.getLogger(__name__)

mq_client = None
finish = False


def bind_ok():
    """
    This callback means the connection to the message queue is ready to use.
    """
    global mq_client
    mq_client.start_listening('physical_timeseries')


def sigterm_handler(sig_no, stack_frame) -> None:
    """
    Handle SIGTERM from docker by closing the mq and db connections and setting a
    flag to tell the main loop to exit.
    """
    global finish

    logger.info(f'{signal.strsignal(sig_no)}, setting finish to True')
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
    global mq_client, finish

    logger.info('===============================================================')
    logger.info('               STARTING LOGICAL MAPPER')
    logger.info('===============================================================')

    mq_client = mq.RabbitMQClient(on_bind_ok=bind_ok, on_message=on_message)
    asyncio.create_task(mq_client.connect())

    while not finish:
        await asyncio.sleep(2)

    while not mq_client.stopped:
        await asyncio.sleep(1)


def on_message(channel, method, properties, body):
    """
    This function is called when a message arrives from RabbitMQ.
    """

    global mq_client, finish

    delivery_tag = method.delivery_tag

    # If the finish flag is set, reject the message so RabbitMQ will re-queue it
    # and return early.
    if finish:
        mq_client._channel.basic_reject(delivery_tag)
        return

    try:
        msg = json.loads(body)

        p_uid = msg[BrokerConstants.PHYSICAL_DEVICE_UID_KEY]
        mapping = dao.get_current_device_mapping(p_uid)
        if mapping is None:
            logger.info(f'No mapping found, creating logical device for physical device uid: {p_uid}.')
            pd = dao.get_physical_device(p_uid)
            if pd is None:
                logger.warning(f'Physical device not found, cannot continue, dropping message.')
                # Reject the message, do not requeue.
                mq_client._channel.basic_reject(delivery_tag, False)
                return

            # Create a logical device and mapping so the message can be published to the logical_timeseries
            # queue. The logical device will be minimal - the same name and location as the physical device.
            # The processes reading the logical_timeseries queue and sending the data onto IoT platforms
            # are responsible for creating the device on the platform and updating the logical device
            # properties with the information they need to recognise the device in future.
            props = {'creation_correlation_id': msg[BrokerConstants.CORRELATION_ID_KEY]}
            ld = LogicalDevice(name=pd.name, location=pd.location, last_seen=pd.last_seen, properties=props)
            logger.info(f'Creating logical device {ld}')
            ld = dao.create_logical_device(ld)
            mapping = PhysicalToLogicalMapping(pd=pd, ld=ld, start_time=datetime.datetime.now(datetime.timezone.utc))
            logger.info(f'Creating mapping {mapping}')
            dao.insert_mapping(mapping)

        #logger.info(f'Forwarding message from {mapping.pd.name} --> {mapping.ld.name}: {msg["timestamp"]} {msg["timeseries"]}')
        msg[BrokerConstants.LOGICAL_DEVICE_UID_KEY] = mapping.ld.uid
        mq_client.publish_message('logical_timeseries', msg)

        # This tells RabbitMQ the message is handled and can be deleted from the queue.    
        mq_client.ack(delivery_tag)

    except BaseException as e:
        logger.warning(f'Caught: {e}')


if __name__ == '__main__':
    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Does not return until SIGTERM is received.
    asyncio.run(main())
    logger.info('Exiting.')
