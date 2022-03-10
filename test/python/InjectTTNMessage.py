import asyncio, json, logging, sys, uuid
import BrokerConstants
from pika.exchange_type import ExchangeType
import api.client.RabbitMQ as mq

#logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
#logger = logging.getLogger(__name__)

tx_channel: mq.TxChannel = None
mq_client: mq.RabbitMQConnection = None
acked = False

async def publish_ack(delivery_tag: int) -> None:
    global acked
    acked = True

async def main():
    global mq_client, tx_channel

    tx_channel = mq.TxChannel(exchange_name=BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME, exchange_type=ExchangeType.fanout)
    tx_channel = mq.TxChannel(exchange_name='ttn_exchange', exchange_type=ExchangeType.direct, on_publish_ack=publish_ack)

    mq_client = mq.RabbitMQConnection(channels=[tx_channel])
    asyncio.create_task(mq_client.connect())

    while not tx_channel.is_open:
        await asyncio.sleep(0)

    # Send a message here
    filename = sys.argv[1]
    print(filename)
    with open(filename, 'r') as f:
        msg = json.load(f)
        correlation_id = str(uuid.uuid4())
        msg_with_cid = {BrokerConstants.CORRELATION_ID_KEY: correlation_id, BrokerConstants.RAW_MESSAGE_KEY: msg}
        tx_channel.publish_message('ttn_raw', msg_with_cid)

    while not acked:
        await asyncio.sleep(0)

    mq_client.stop()
    while not mq_client.stopped:
        await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())
