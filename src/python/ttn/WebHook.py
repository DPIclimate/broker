import asyncio, datetime, json, logging, os
from fastapi import FastAPI, Response
from typing import Any, Dict

import api.client.RabbitMQ as mq


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
logger = logging.getLogger(__name__)

_cache_dir = f'{os.getenv("HOME")}/ttn_incoming_msgs'
os.makedirs(name=_cache_dir, mode=0o700, exist_ok=True)

lock = asyncio.Lock()

app = FastAPI()
ep = None
mq_ready = False

def create_queue():
    global ep
    ep.queue_declare('ttn_webhook')


def bind_ok():
    global mq_ready
    mq_ready = True


@app.on_event("startup")
async def startup() -> None:
    global ep, mq_ready

    user = os.environ['RABBITMQ_DEFAULT_USER']
    passwd = os.environ['RABBITMQ_DEFAULT_PASS']
    host = os.environ['RABBITMQ_HOST']
    port = os.environ['RABBITMQ_PORT']

    ep = mq.ExamplePublisher(f'amqp://{user}:{passwd}@{host}:{port}/%2F', on_exchange_ok=create_queue, on_bind_ok=bind_ok)
    asyncio.create_task(ep.connect())

    while not mq_ready:
        await asyncio.sleep(0)


JSONObject = Dict[str, Any]


@app.post("/ttn/webhook/up")
async def webhook_endpoint(msg: JSONObject) -> None:
    """
    Receive webhook calls from TTN.
    """

    global ep, lock
    #if 'simulated' in msg and msg['simulated']:
    #    print('Ignoring simulated message.')
    #    return

    async with lock:
        # Write the message to a local cache directory. Remove the message file once the
        # message has been written to RabbitMQ on the assumption it will be persisted there.
        with open(get_cache_filename(msg), 'w') as f:
            json.dump(msg, f)

        ep.publish_message(msg)

    # Doing an explicit return of a Response object with the 204 code to avoid
    # the default FastAPI behaviour of always sending a response body. Even if
    # a path method returns None, FastAPI will return a body containing "null"
    # or similar. TTN does nothing with the response, so there is no pointing
    # sending it one.
    return Response(status_code=204)


def get_cache_filename(msg: JSONObject) -> str:
    app_id = msg['end_device_ids']['application_ids']['application_id']
    dev_id = msg['end_device_ids']['device_id']

    received_at = datetime.datetime.now(datetime.timezone.utc)
    if 'received_at' in msg:
        received_at = msg['received_at']

    return f'{_cache_dir}/{app_id}-{dev_id}-{received_at}.json'