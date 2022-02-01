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

ep = None
finish = False

def create_queue():
    global ep
    ep.queue_declare('ttn_webhook')


def bind_ok():
    global ep
    ep.start_listening('ttn_webhook')


def sigterm_handler(sig_no, stack_frame) -> None:
    global finish

    logger.info(f'Caught {signal.strsignal(sig_no)}, setting finish to True')
    finish = True
    ep.stop()


async def main():
    global ep, finish

    logger.info('===============================================================')
    logger.info('               STARTING TTN ALLMSGSWRITER')
    logger.info('===============================================================')

    user = os.environ['RABBITMQ_DEFAULT_USER']
    passwd = os.environ['RABBITMQ_DEFAULT_PASS']
    host = os.environ['RABBITMQ_HOST']
    port = os.environ['RABBITMQ_PORT']

    ep = mq.ExamplePublisher(f'amqp://{user}:{passwd}@{host}:{port}/%2F', on_exchange_ok=create_queue, on_bind_ok=bind_ok, on_message=callback)
    asyncio.create_task(ep.connect())

    while not finish:
        await asyncio.sleep(2)
    
    while not ep.stopped:
        await asyncio.sleep(1)


def callback(channel, method, properties, body):
    global ep, finish

    # If the finish flag is set, exit without doing anything and do not
    # ack the message, so it stays on the queue.
    if finish:
        return

    delivery_tag = method.delivery_tag

    try:
        msg = json.loads(body)
        last_seen = None
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
            logger.warning(f'Found {len(devs)} devices: {devs}')
    
        ep.ack(delivery_tag)

    except BaseException as e:
        print(f'Device not found, creating physical device. Caught: {e}')



if __name__ == '__main__':
    signal.signal(signal.SIGTERM, sigterm_handler)
    asyncio.run(main())
    logger.info('Exiting.')
