#
# TODO:
# 
# Test the behaviour when the DB is not available or fails.
# Ensure RabbitMQ messages are not ack'd so they can be re-delivered. Figure out how to get
# RabbitMQ to re-deliver them.
#
# See if there is a way to catch docker shutting the process down and close the mq & db
# connections nicely.
#

import datetime
import dateutil.parser

import asyncio, json, logging, os, signal

from pdmodels.Models import PhysicalDevice, Location
import api.client.RabbitMQ as mq
import api.client.TTNAPI as ttn

import db.DAO as dao

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
logger = logging.getLogger('AllMsgsWriter') # Shows as __main__ if __name__ is used.

mq_client = None
finish = False

def create_queue():
    global mq_client
    mq_client.queue_declare('ttn_webhook')


def bind_ok():
    """
    This callback means the connection to the message queue is ready to use.
    """
    global mq_client
    mq_client.start_listening('ttn_webhook')


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
    logger.info('               STARTING TTN ALLMSGSWRITER')
    logger.info('===============================================================')

    user = os.environ['RABBITMQ_DEFAULT_USER']
    passwd = os.environ['RABBITMQ_DEFAULT_PASS']
    host = os.environ['RABBITMQ_HOST']
    port = os.environ['RABBITMQ_PORT']

    mq_client = mq.RabbitMQClient(f'amqp://{user}:{passwd}@{host}:{port}/%2F', on_exchange_ok=create_queue, on_bind_ok=bind_ok, on_message=on_message)
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

    # If the finish flag is set, exit without doing anything. Do not
    # ack the message so it stays on the queue.
    if finish:
        return

    delivery_tag = method.delivery_tag

    try:
        msg = json.loads(body)
        last_seen = None
        # We should always get a value in the message for this, but default to 'now'
        # just in case.
        received_at = datetime.datetime.now(datetime.timezone.utc)

        if 'received_at' in msg:
            received_at = msg['received_at']
            last_seen = dateutil.parser.isoparse(received_at)

        app_id = msg['end_device_ids']['application_ids']['application_id']
        dev_id = msg['end_device_ids']['device_id']

        devs = dao.get_physical_devices(query_args={'prop_name': ['app_id', 'dev_id'], 'prop_value': [app_id, dev_id]})
        if len(devs) < 1:
            logger.info('Device not found, creating physical device.')
            ttn_dev = ttn.get_device_details(app_id, dev_id)
            print(f'Device info from TTN: {ttn_dev}')

            dev_name = ttn_dev['name'] if 'name' in ttn_dev else dev_id
            dev_loc = Location.from_ttn_device(ttn_dev)
            props = {'app_id': app_id, 'dev_id': dev_id }

            dev = PhysicalDevice(source_name='ttn', name=dev_name, location=dev_loc, last_seen=last_seen, properties=props)
            dao.create_physical_device(dev)
        elif len(devs) == 1:
            dev = devs[0]
            logger.info(f'Updating last_seen for device {dev.name}')

            if last_seen != None:
                dev.last_seen = last_seen
                dev = dao.update_physical_device(dev.uid, dev)
        else:
            # Could use the device with the lowest uid because it would have been created first and
            # later ones are erroneous dupes.
            logger.warning(f'Found {len(devs)} devices: {devs}')

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
