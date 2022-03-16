import datetime
import dateutil.parser

import asyncio, json, logging, signal, uuid
from typing import Optional

import BrokerConstants
from pdmodels.Models import PhysicalDevice, Location
from pika.exchange_type import ExchangeType

import api.client.RabbitMQ as mq
import api.client.TTNAPI as ttn

import api.client.DAO as dao

import util.LoggingUtil as lu

rx_channel: mq.RxChannel = None
#tx_channel: mq.TxChannel = None
mq_client: mq.RabbitMQConnection = None
finish = False

def sigterm_handler(sig_no, stack_frame) -> None:
    """
    Handle SIGTERM from docker by closing the mq and db connections and setting a
    flag to tell the main loop to exit.
    """
    global finish, mq_client

    logging.debug(f'{signal.strsignal(sig_no)}, setting finish to True')
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
    global mq_client, rx_channel, tx_channel, finish

    logging.info('===============================================================')
    logging.info('               STARTING YDOC LISTENER')
    logging.info('===============================================================')

    # Cannot put these assignments up the top because you cannot do a forward
    # declaration of a function in Python (in this case, on_message).
    rx_channel = mq.RxChannel('amq.topic', exchange_type=ExchangeType.topic, queue_name='ydoc_listener', on_message=on_message, routing_key='.YDOC.#')
    #tx_channel = mq.TxChannel(exchange_name=BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME, exchange_type=ExchangeType.fanout)
    mq_client = mq.RabbitMQConnection(channels=[rx_channel])
    asyncio.create_task(mq_client.connect())

    #while not (rx_channel.is_open and tx_channel.is_open):
    while not (rx_channel.is_open):
        await asyncio.sleep(0)

    while not finish:
        await asyncio.sleep(2)

    while not mq_client.stopped:
        await asyncio.sleep(1)


def parse_ydoc_ts(ydoc_ts) -> Optional[datetime.datetime]:
    """
    The YDOC dataloggers provide a timestamp in UTC+10:00 with the format YYMMDDHHmmSS, eg 220316111505.
    """
    try:
        ydoc_ts_str = str(ydoc_ts)
        ts = datetime.datetime(
            year=int(ydoc_ts_str[0:2]) + 2000,
            month=int(ydoc_ts_str[2:4]),
            day=int(ydoc_ts_str[4:6]),
            hour=int(ydoc_ts_str[6:8]),
            minute=int(ydoc_ts_str[8:10]),
            second=int(ydoc_ts_str[10:12]),
            tzinfo=datetime.timezone(datetime.timedelta(hours=10)))
        return ts
    except Exception as err:
        logging.exception('parse_ydoc_ts error.')
    
    return None


def on_message(channel, method, properties, body):
    """
    This function is called when a message arrives from RabbitMQ.
    """
    global rx_channel, tx_channel, finish

    delivery_tag = method.delivery_tag

    # If the finish flag is set, reject the message so RabbitMQ will re-queue it
    # and return early.
    if finish:
        rx_channel._channel.basic_reject(delivery_tag)
        return

    try:
        """
        {'device': {'sn': 108172923, 'name': 'House Paddock Rip 3 ', 'v': '4.4B6', 'imei': 352909081729234, 'sim': 89882280666027703515},
         'channels': [ {'code': 'P1', 'name': 'Par1', 'unit': ''},
                       {'code': 'P1*', 'name': 'Par1*', 'unit': ''},
                       {'code': 'SB', 'name': 'Signal', 'unit': 'bars'},
                       {'code': 'SDB', 'name': 'Signal strength', 'unit': 'dBm'},
                       {'code': 'AVGVi', 'name': 'Average voltage', 'unit': 'V'},
                       {}],
         'data': [ {'$ts': 220316093000, '$msg': 'WDT;Soil Sensor 1 '},
                   {'$ts': 220316093005, '$msg': 'WDT;Soil Sensor 2'},
                   {'$ts': 220316093005, 'P1': '0*T', 'P1*': '0*T', 'AVGVi': 3.31},
                   {}]}
        """
        # The message from the webhook process already has the correlation id in it.
        correlation_id = str(uuid.uuid4())
        lu.cid_logger.debug(f'Message as received: {body}', extra={BrokerConstants.CORRELATION_ID_KEY: correlation_id})

        msg = json.loads(body)
        msg_with_cid = {BrokerConstants.CORRELATION_ID_KEY: correlation_id, BrokerConstants.RAW_MESSAGE_KEY: msg}

        lu.cid_logger.info(f'Accepted message {msg}', extra=msg_with_cid)

        if 'data' not in msg:
            lu.cid_logger.info(f'Ignoring message because it has no data element.', extra=msg_with_cid)
            rx_channel._channel.basic_ack(delivery_tag)
            return

        serial_no = msg['device']['sn']
        dev_name = msg['device']['name']

        channels = {}
        for c in msg['channels']:
            if 'code' in c:
                channels[c['code']] = c

        last_seen = None
        data = msg['data']
        dots = []
        """
        A message from a YDOC device can have multiple sets of readings under the data element,
        with each set having its own timestamp. So go through the sets of readings and create
        data points (dots) from each reading in each set with the associated timestamp (in ISO-8601 format).

        The timestamps are also used for the last seen value of the physical device. The parse_ydoc_ts
        function returns a datetime.datetime object because this makes it simple to compare the current
        last seen value with the timestamp from the set of readings. After the last seen is taken care
        of the timestamp is converted to ISO format for use in the phsical timeseries message.
        """
        for d in data:
            for k, v in d.items():
                if k == '$ts':
                    ts = parse_ydoc_ts(v)
                    if last_seen is None or last_seen < ts:
                        last_seen = ts

                    ts = ts.isoformat()
                    continue
                if k == '$msg':
                    lu.cid_logger.debug(f'Ignoring message element: {v}', extra=msg_with_cid)
                    break
                if not k in channels:
                    continue

                dot = { 'ts': ts, 'name': k, 'value': v }
                dots.append(dot)

        lu.cid_logger.info(dots, extra=msg_with_cid)

        source_ids = {
            # These values are split out to make SQL queries more readable and hopefully faster.
            'serial': serial_no
        }

        pds = dao.get_pyhsical_devices_using_source_ids(BrokerConstants.YDOC, source_ids)
        if len(pds) < 1:
            lu.cid_logger.info('Device not found, creating physical device.', extra=msg_with_cid)
            #dev_loc = Location.from_ttn_device(ttn_dev)
            props = {
                BrokerConstants.YDOC: msg,
                BrokerConstants.CREATION_CORRELATION_ID_KEY: correlation_id
            }

            pd = PhysicalDevice(source_name=BrokerConstants.YDOC, name=dev_name, location=None, last_seen=last_seen, source_ids=source_ids, properties=props)
            pd = dao.create_physical_device(pd)
        else:
            pd = pds[0]
            #logging.info(f'Updating last_seen for device {pd.name}')
            if last_seen is not None:
                pd.last_seen = last_seen
                pd = dao.update_physical_device(pd)

        if pd is None:
            lu.cid_logger.error(f'Physical device not found, message processing ends now. {correlation_id}', extra=msg_with_cid)
            rx_channel._channel.basic_ack(delivery_tag)
            return


        """
        # Record the message to the all messages table before doing anything else to ensure it
        # is saved. Attempts to add duplicate messages are ignored in the DAO.
        dao.add_raw_json_message(BrokerConstants.TTN, last_seen, correlation_id, msg)


        """

        # This tells RabbitMQ the message is handled and can be deleted from the queue.    
        rx_channel._channel.basic_ack(delivery_tag)
        lu.cid_logger.debug('Acking message from ttn_raw.', extra=msg_with_cid)
    except Exception as e:
        logging.exception('Error while processing message.')
        rx_channel._channel.basic_ack(delivery_tag)


if __name__ == '__main__':
    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Does not return until SIGTERM is received.
    asyncio.run(main())
    logging.info('Exiting.')
