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

import datetime
import dateutil.parser

import asyncio, json, logging, math, os, signal

from pdmodels.Models import PhysicalDevice, Location, LogicalDevice, PhysicalToLogicalMapping
import api.client.RabbitMQ as mq

import db.DAO as dao

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
logger = logging.getLogger('LogicalMapper') # Shows as __main__ if __name__ is used.

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

    ttn_raw message is the json as received by the ttn uplink webhook.

    physical_timeseries has:
    {'physical_uid': physical_dev_uid, 'timestamp': iso_8601_timestamp, 'timeseries': [ {'ts_key': value}, ...]}

    logical_timeseries has (not sure if physical dev uid is useful, discuss):
    {'physical_uid': physical_dev_uid, 'logical_uid': logical_dev_uid, , 'timestamp': iso_8601_timestamp, 'timeseries': [ {'ts_key': value}, ...]}
    """

    global mq_client, finish

    # If the finish flag is set, exit without doing anything. Do not
    # ack the message so it stays on the queue.
    if finish:
        return

    delivery_tag = method.delivery_tag

    try:
        msg = json.loads(body)

        mapping = dao.get_current_device_mapping(msg['physical_uid'])
        if mapping is not None:
            logger.info(f'Forwarding message from {mapping.pd.name} --> {mapping.ld.name}: {msg["timestamp"]} {msg["timeseries"]}')
            msg['logical_uid'] = mapping.ld.uid
            mq_client.publish_message('logical_timeseries', msg)
        else:
            logger.warn(f'No mapping found, must create logical device for physical device uid: {msg["physical_uid"]}.')

        # This tells RabbitMQ the message is handled and can be deleted from the queue.    
        mq_client.ack(delivery_tag)

    except BaseException as e:
        print(f'Device not found, creating physical device. Caught: {e}')


if __name__ == '__main__':
    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Does not return until SIGTERM is received.
    asyncio.run(main())
    logger.info('Exiting.')
