#
# TODO:
#
# Find a way to make the cached message files persistent between runs of the container
# so it can read them and send them to RabbitMQ on startup.
#
# Also read through the files after a RabbitMQ re-connection to send pending messages
# over the new connection.
#

import asyncio, datetime, json, logging, os
from numbers import Integral
from fastapi import FastAPI, Response
from typing import Any, Dict

import api.client.RabbitMQ as mq


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
logger = logging.getLogger(__name__)

#
# An interesting point about os.makedirs: apparently in more recent versions
# of python 3.10+ the given permission is only applied to the final directory of the
# path. Other directories use the users default mode.
#
# Because we're creating a directory right under $HOME there are not really
# any intermediate directories so this is ok and we get all the right permissions.
_cache_dir = f'{os.getenv("HOME")}/ttn_incoming_msgs'
os.makedirs(name=_cache_dir, mode=0o700, exist_ok=True)

#
# This is used to try and guarantee only one operation is happening to the
# message queue at time.
#
# Given we're doing single-threaded async processing rather than multi-threaded
# processing I'm not sure it's necessary but I'm wondering what would happen if
# pika has just published a message but hasn't started reading the reply from the
# server, and then another webhook hit comes in and we try to publish another
# message to RabbitMQ.
lock = asyncio.Lock()

app = FastAPI()

mq_client = None
mq_ready = False


def bind_ok():
    global mq_ready
    mq_ready = True

    # Now is the time to read messages stored on disk and
    # send them to RabbitMQ.


async def publish_ack(delivery_tag: Integral) -> None:
    """
    RabbitMQ is telling us the message is safely stored so we can
    delete the cache file from disk.

    The message may not have been delivered yet but it should survive
    a RabbitMQ restart.
    """
    global lock, unacked_messages

    async with lock:
        if delivery_tag in unacked_messages:
            filename = unacked_messages.pop(delivery_tag)
            if os.path.isfile(filename):
                logger.debug(f'Removing cache file: {filename}')
                os.remove(filename)
            else:
                logger.warning(f'cache file {filename} does not exist.')
        else:
            logger.warning(f'delivery_tag {delivery_tag} not in unacked_messages.')


@app.on_event("startup")
async def startup() -> None:
    global mq_client, mq_ready

    mq_client = mq.RabbitMQClient(on_bind_ok=bind_ok, on_publish_ack=publish_ack)
    asyncio.create_task(mq_client.connect())

    # Wait for the RabbitMQ connection/channel/queue everything to be
    # ready to use. asyncio.sleep(0) is supposed to be a special case
    # that allows control to be passed back to the asyncio event loop
    # quickly.
    while not mq_ready:
        await asyncio.sleep(0)


JSONObject = Dict[str, Any]

# A dict of delivery_tag -> filename for keeping track of which
# messages have not been ack'd by RabbitMQ. When a delivery
# confirmation arrives it means we can delete that cache file
# from disk. The delivery confirmation only means RabbitMQ has
# received the message and persisted it, not that that it has
# been received or ack'd by the queue reader(s).
unacked_messages = {}

@app.post("/ttn/webhook/up")
async def webhook_endpoint(msg: JSONObject) -> None:
    """
    Receive webhook calls from TTN.
    """

    global mq_client, lock, unacked_messages
    #if 'simulated' in msg and msg['simulated']:
    #    print('Ignoring simulated message.')
    #    return

    async with lock:
        # Write the message to a local cache directory. It will be removed
        # when RabbitMQ acks receipt of the message.
        filename = get_cache_filename(msg)
        with open(filename, 'w') as f:
            json.dump(msg, f)

        delivery_tag = mq_client.publish_message('ttn_raw', msg)
        unacked_messages[delivery_tag] = filename

    # Doing an explicit return of a Response object with the 204 code to avoid
    # the default FastAPI behaviour of always sending a response body. Even if
    # a path method returns None, FastAPI will return a body containing "null"
    # or similar. TTN does nothing with the response, so there is no pointing
    # sending it one.
    return Response(status_code=204)


def get_cache_filename(msg: JSONObject) -> str:
    """
    Generate a fully-qualified filename for a message cache file.
    """
    app_id = msg['end_device_ids']['application_ids']['application_id']
    dev_id = msg['end_device_ids']['device_id']

    received_at = datetime.datetime.now(datetime.timezone.utc)
    if 'received_at' in msg:
        received_at = msg['received_at']

    return f'{_cache_dir}/{app_id}-{dev_id}-{received_at}.json'
