"""
This program receives logical device timeseries messages and forwards them
on to Ubidots.
"""

import datetime
import dateutil.parser

import asyncio, json, logging, math, os, signal

from pdmodels.Models import LogicalDevice
import api.client.RabbitMQ as mq
import api.client.Ubidots as ubidots

import db.DAO as dao

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
logger = logging.getLogger(__name__) # Shows as __main__ if __name__ is used.

mq_client = None
finish = False


def bind_ok():
    """
    This callback means the connection to the message queue is ready to use.
    """
    global mq_client
    mq_client.start_listening('logical_timeseries')


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
    logger.info('               STARTING UBIDOTS WRITER')
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

    logical_timeseries has (not sure if physical dev uid is useful, discuss):
    {
        "physical_uid": 27,
        "logical_uid": 16,
        "timestamp": "2022-02-04T00:32:28.392595503Z",
        "timeseries": [
            {"name": "battery", "value": 3.5},
            {"name": "humidity", "value": 95.11},
            {"name": "temperature", "value": 4.87}
        ]
    }

    This needs to be transformed to:

    {
        'battery': {'value': 3.6, 'timestamp': 1643934748392},
        'humidity': {'value': 37.17, 'timestamp': 1643934748392},
        'temperature': {'value': 37.17, 'timestamp': 1643934748392}
    }

    So get the logical device from the db via the id in the message, and convert the iso-8601 timestamp to an epoch-style timestamp.
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

        l_uid = msg['logical_uid']

        # Temporary hack to only process messages from David's netvox.
        if l_uid != 159:
            mq_client.ack(delivery_tag)
            return

        ld = dao.get_logical_device(l_uid)
        if ld is None:
            logging.warning(f'Could not find logical device for message: {body}')
            mq_client.ack(delivery_tag)
            return

        #logger.info(f'Logical device from mapping: {ld}')

        ts_float = dateutil.parser.isoparse(msg['timestamp']).timestamp()
        # datetime.timestamp() returns a float where the ms are to the right of the
        # decimal point. This should get us an integer value in ms.
        ts = math.floor(ts_float * 1000)

        ubidots_payload = {}
        for v in msg['timeseries']:
            ubidots_payload[v['name']] = {'value': v['value'], 'timestamp': ts}

        # It seems the ubidots device LABEL must be used here, probably because
        # the POST is using the 1.6 API.

        # TODO: Put the Ubidots device JSON into a key within properties so it
        # is one level down. That way other end-points can store their own
        # metadata under their own key.

        new_device = False
        if not 'label' in ld.properties:
            # If the label is not in the logical device properties it most likely
            # means the logical device is newly created by the mapper. Look at the
            # physical device source to decide what the label should be, and remember
            # to read the Ubidots device back after writing the timeseries data so
            # the device info can be stored in the logical device properties.
            logger.info('No Ubidots label found in logical device.')
            pd = dao.get_physical_device(msg['physical_uid'])
            if pd is None:
                logging.warning(f'Could not find physical device for message: {body}')
                mq_client.ack(delivery_tag)
                return

            new_device = True
            if pd.source_name == 'ttn':
                ld.properties['label'] = pd.properties['dev_eui']
                logger.info(f'Using physical device eui for label: {ld.properties["label"]}')
            else:
                logging.warning(f'TODO: work with {pd.source_name} devices!')
                mq_client.ack(delivery_tag)
                return

        ubidots_dev_label = ld.properties['label']
        ubidots.post_device_data(ubidots_dev_label, ubidots_payload)

        if new_device:
            # Update the newly created logical device properties with the information
            # returned from Ubidots, but nothing else. We don't want to overwite the
            # last_seen value because that should be set to the timestamp from the
            # message, which was done in the mapper process.
            logger.info('Updating new logical device properties from Ubidots.')
            ud = ubidots.get_device(ubidots_dev_label)
            if ud is not None:
                ld.properties = ud.properties
                logger.info(f'updated ld: {ld}')
                dao.update_logical_device(ld.uid, ld)

    except BaseException as e:
        logger.warning(f'Caught: {e}')

    # This tells RabbitMQ the message is handled and can be deleted from the queue.    
    mq_client.ack(delivery_tag)


if __name__ == '__main__':
    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Does not return until SIGTERM is received.
    asyncio.run(main())
    logger.info('Exiting.')
