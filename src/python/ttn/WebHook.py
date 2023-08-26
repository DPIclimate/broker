#
# TODO:
#
# Find a way to make the cached message files persistent between runs of the container
# so it can read them and send them to RabbitMQ on startup.
#
import logging
import util.LoggingUtil as lu

import asyncio, datetime, json, os, uuid
from fastapi import BackgroundTasks, FastAPI, Response
from pathlib import Path
from typing import Any, Dict

from pika.exchange_type import ExchangeType

import BrokerConstants
import api.client.RabbitMQ as mq

_cache_dir = Path(f'{os.getenv("HOME")}/ttn_incoming_msgs')
_cache_dir.mkdir(exist_ok=True)

# Prometheus metrics
from prometheus_client import Counter, start_http_server
request_counter = Counter('ttn_requests_total', 'Total number of incoming requests to TTN webhook')
# Start up the server to expose the metrics.
start_http_server(8000)

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
tx_channel = None

# A dict of delivery_tag -> filename for keeping track of which
# messages have not been ack'd by RabbitMQ. When a delivery
# confirmation arrives it means we can delete that cache file
# from disk. The delivery confirmation only means RabbitMQ has
# received the message and persisted it, not that that it has
# been received or ack'd by the queue reader(s).
unacked_messages = {}

JSONObject = Dict[str, Any]

async def publish_msg(msg_with_cid: JSONObject) -> None:
    global lock, tx_channel, unacked_messages
    filename = get_cache_filename(msg_with_cid[BrokerConstants.RAW_MESSAGE_KEY])

    if tx_channel.is_open:
        async with lock:
            delivery_tag = tx_channel.publish_message('ttn_raw', msg_with_cid)
            lu.cid_logger.debug(f'Published message {delivery_tag} to RabbitMQ', extra=msg_with_cid)

            # FIXME: Can't have this dict growing endlessly if RabbitMQ
            # is down. Perhaps rename the file here to the delivery_tag
            # and then we don't need to track it.
            unacked_messages[delivery_tag] = filename


async def process_msg_files() -> None:
    logging.info(f'Looking for message files in {_cache_dir}')

    if mq_client.state == mq.State.CLOSING or mq_client.state == mq.State.CLOSED:
        logging.info('Cannot process message files when MQ connection is closed.')
        return

    while mq_client.state != mq.State.OPEN:
        await asyncio.sleep(0)

    for msg_file in _cache_dir.iterdir():
        if msg_file.is_file() and msg_file.suffix == '.json':
            with open(msg_file, 'r') as f:
                msg = json.load(f)
                lu.cid_logger.info(f'Processing file {str(msg_file)}', extra=msg)
                await publish_msg(msg)


async def tx_channel_ready(obj) -> None:
    logging.info('tx channel ready.')
    asyncio.create_task(process_msg_files())


async def publish_ack(delivery_tag: int) -> None:
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
                logging.debug(f'Removing cache file: {filename} due to ack for msg {delivery_tag}')
                os.remove(filename)
            else:
                logging.warning(f'cache file {filename} does not exist.')
        else:
            logging.warning(f'delivery_tag {delivery_tag} not in unacked_messages.')


@app.on_event("startup")
async def startup() -> None:
    global mq_client, tx_channel

    tx_channel = mq.TxChannel(exchange_name='ttn_exchange', exchange_type=ExchangeType.direct, on_ready=tx_channel_ready, on_publish_ack=publish_ack)
    mq_client = mq.RabbitMQConnection([tx_channel])
    asyncio.create_task(mq_client.connect())


@app.post("/ttn/webhook/up")
async def webhook_endpoint(msg: JSONObject, background_tasks: BackgroundTasks) -> None:
    # Increment the request counter
    request_counter.inc()

    """
    Receive webhook calls from TTN.
    """

    global tx_channel, lock
    #if 'simulated' in msg and msg['simulated']:
    #    print('Ignoring simulated message.')
    #    return

    # Write the message to a local cache directory. It will be removed
    # when RabbitMQ acks receipt of the message.
    # NOTE: The string representation of the UUID is put into the message, not the UUID object.
    correlation_id = str(uuid.uuid4())
    msg_with_cid = {BrokerConstants.CORRELATION_ID_KEY: correlation_id, BrokerConstants.RAW_MESSAGE_KEY: msg}
    end_device_ids = msg['end_device_ids']
    dev_id = end_device_ids['device_id']
    app_ids = end_device_ids['application_ids']
    app_id = app_ids['application_id']

    lu.cid_logger.info(f'Accepted message from {app_id}:{dev_id}', extra=msg_with_cid)

    filename = get_cache_filename(msg)
    with open(filename, 'w') as f:
        json.dump(msg_with_cid, f)

    if tx_channel.is_open:
        background_tasks.add_task(publish_msg, msg_with_cid)

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


