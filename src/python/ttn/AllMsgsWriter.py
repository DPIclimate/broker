#
# TODO:
# 
# Test the behaviour when the REST API is not available or fails (such as if the DB is down).
# Ensure RabbitMQ messages are not ack'd so they can be re-delivered. Figure out how to get
# RabbitMQ to re-deliver them.
#

import datetime
import dateutil.parser

import asyncio, json, logging, os
from pika.exchange_type import ExchangeType

from pdmodels.Models import PhysicalDevice, Location
import api.client.BrokerAPI as broker
import api.client.RabbitMQ as mq
import api.client.TTNAPI as ttn

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
logger = logging.getLogger(__name__)

ep = None

def create_queue():
    global ep
    ep.queue_declare('ttn_webhook')


def bind_ok():
    global ep
    ep.start_listening('ttn_webhook')


async def main():
    global ep

    user = os.environ['RABBITMQ_DEFAULT_USER']
    passwd = os.environ['RABBITMQ_DEFAULT_PASS']
    host = os.environ['RABBITMQ_HOST']
    port = os.environ['RABBITMQ_PORT']

    ep = mq.ExamplePublisher(f'amqp://{user}:{passwd}@{host}:{port}/%2F', on_exchange_ok=create_queue, on_bind_ok=bind_ok, on_message=callback)
    asyncio.create_task(ep.connect())

    while True:
        await asyncio.sleep(60)


def callback(channel, method, properties, body):
    global ep

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

        dev = broker.get_physical_device(app_id, dev_id)

        if last_seen != None:
            dev.last_seen = last_seen
            dev = broker.update_physical_device(dev)

    except:
        print('Device not found, creating physical device.')
        ttn_dev = ttn.get_device_details(app_id, dev_id)
        print(f'Device info from TTN: {ttn_dev}')

        dev_name = ttn_dev['name'] if 'name' in ttn_dev else dev_id
        dev_loc = Location.from_ttn_device(ttn_dev)
        props = {'app_id': app_id, 'dev_id': dev_id }

        dev = PhysicalDevice(source_name='ttn', name=dev_name, location=dev_loc, last_seen=last_seen, properties=props)
        broker.create_physical_device(dev)

    ep.ack(delivery_tag)


if __name__ == '__main__':
    asyncio.run(main())
