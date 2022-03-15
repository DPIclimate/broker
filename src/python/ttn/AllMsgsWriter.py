#
# TODO:
# 
# Test the behaviour when the DB is not available or fails.
#

import datetime
import dateutil.parser

import asyncio, json, logging, os, requests, signal
from typing import Optional

import BrokerConstants
from pdmodels.Models import PhysicalDevice, Location
from pika.exchange_type import ExchangeType

import api.client.RabbitMQ as mq
import api.client.TTNAPI as ttn

import api.client.DAO as dao

import util.LoggingUtil as lu

rx_channel: mq.RxChannel = None
tx_channel: mq.TxChannel = None
mq_client: mq.RabbitMQConnection = None
finish = False

_enabled_apps = os.getenv('TTN_ENABLED_APPS')
if _enabled_apps is not None and len(_enabled_apps) > 0:
    _enabled_apps = _enabled_apps.split(',')

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
    logging.info('               STARTING TTN ALLMSGSWRITER')
    logging.info('===============================================================')

    # Cannot put these assignments up the top because you cannot do a forward
    # declaration of a function in Python (in this case, on_message).
    rx_channel = mq.RxChannel('ttn_exchange', exchange_type=ExchangeType.direct, queue_name='ttn_raw', on_message=on_message, routing_key='ttn_raw')
    tx_channel = mq.TxChannel(exchange_name=BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME, exchange_type=ExchangeType.fanout)
    mq_client = mq.RabbitMQConnection(channels=[rx_channel, tx_channel])
    asyncio.create_task(mq_client.connect())

    while not (rx_channel.is_open and tx_channel.is_open):
        await asyncio.sleep(0)

    while not finish:
        await asyncio.sleep(2)

    while not mq_client.stopped:
        await asyncio.sleep(1)


def get_received_at(msg) -> Optional[str]:
    """
    Return a received_at field from a message as a string.

    The uplink_message.received_at field is preferred as that is the time
    the gateway received the message so closest to when the device sent it.
    It is also the value used by the ubifunction.

    If that is not present the received_at field at the message level will be
    used.

    Returns None if neither of those fields are found.
    """

    received_at = None
    if 'received_at' in msg:
        received_at = msg['received_at']
    if 'uplink_message' in msg:
        uplink_message = msg['uplink_message']
        if 'received_at' in uplink_message:
            received_at = uplink_message['received_at']

    return received_at

_decoder_req_headers = {
    'Content-type': 'application/json',
    'Accept': 'application/json'
}

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
        # The message from the webhook process already has the correlation id in it.
        msg_with_cid = json.loads(body)

        msg = msg_with_cid[BrokerConstants.RAW_MESSAGE_KEY]
        correlation_id = msg_with_cid[BrokerConstants.CORRELATION_ID_KEY]

        app_id = msg['end_device_ids']['application_ids']['application_id']
        dev_id = msg['end_device_ids']['device_id']
        dev_eui = msg['end_device_ids']['dev_eui'].lower()

        lu.cid_logger.info(f'Accepted message from {app_id}:{dev_id}', extra=msg_with_cid)

        last_seen = None
        received_at = get_received_at(msg)
        # We should always get a value in the message for this, but default to 'now' just in case.
        if received_at is None:
            lu.cid_logger.warning(f'Defaulting received_at to \'now\' bcause it was not found in a message from device {app_id}/{dev_id}.', extra=msg_with_cid)
            received_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        last_seen = dateutil.parser.isoparse(received_at)

        source_ids = {
            # These values are split out to make SQL queries more readable and hopefully faster.
            'app_id': app_id,
            'dev_id': dev_id,
            'dev_eui': dev_eui,
        }

        # Record the message to the all messages table before doing anything else to ensure it
        # is saved. Attempts to add duplicate messages are ignored in the DAO.
        dao.add_raw_json_message(BrokerConstants.TTN, last_seen, correlation_id, msg)

        pds = dao.get_pyhsical_devices_using_source_ids(BrokerConstants.TTN, source_ids)
        if len(pds) < 1:
            lu.cid_logger.info('Device not found, creating physical device.', extra=msg_with_cid)
            ttn_dev = ttn.get_device_details(app_id, dev_id)
            lu.cid_logger.info(f'Device info from TTN: {ttn_dev}', extra=msg_with_cid)

            dev_name = ttn_dev['name'] if 'name' in ttn_dev else dev_id
            dev_loc = Location.from_ttn_device(ttn_dev)
            source_ids = {
                # These values are split out to make SQL queries more readable and hopefully faster.
                'app_id': app_id,
                'dev_id': dev_id,
                'dev_eui': dev_eui,
            }

            props = {
                BrokerConstants.TTN: ttn_dev,
                BrokerConstants.CREATION_CORRELATION_ID_KEY: correlation_id
            }

            pd = PhysicalDevice(source_name=BrokerConstants.TTN, name=dev_name, location=dev_loc, last_seen=last_seen, source_ids=source_ids, properties=props)
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

        uplink_message = msg['uplink_message'] if 'uplink_message' in msg else None
        if uplink_message is not None:
            decoded_payload = None
            try:
                def serialise_datetime(obj):
                    if isinstance(obj, datetime.datetime):
                        return obj.isoformat()
                    lu.cid_logger.warning(f'Cannot serialise {type(obj)}, {obj}', extra=msg_with_cid)
                    return "NO CONVERSION"

                #pd.properties['decoder_name'] = 'temphumid-netvox-r718a'
                data = json.dumps({'device':pd.dict(), 'message':msg}, default=serialise_datetime)
                lu.cid_logger.debug(data, extra=msg_with_cid)
                r = requests.post('http://ttn_decoder:3001/', headers=_decoder_req_headers, data=data)
                if r.status_code != 200:
                    lu.cid_logger.error(f'Decoding failed for {app_id}:{dev_id} {correlation_id}', extra=msg_with_cid)
                else:
                    decoded_payload = r.json()
                    if 'data' in decoded_payload:
                        decoded_payload = decoded_payload['data']
                        lu.cid_logger.debug(f'Broker decoded payload: {decoded_payload}', extra=msg_with_cid)
                    else:
                        lu.cid_logger.warning(f'No data element in {decoded_payload}', extra=msg_with_cid)

            except Exception as err:
                lu.cid_logger.exception('Local decoding of message failed.', extra=msg_with_cid)

            # This is a temporary check to confirm local decoders are working.
            if decoded_payload is not None and 'decoded_payload' in uplink_message:
                uplink_decode = uplink_message['decoded_payload']
                lu.cid_logger.debug(f'ttn decode: {uplink_decode}', extra=msg_with_cid)
                lu.cid_logger.debug(f'Checking if local and ttn decode are the same: {decoded_payload == uplink_decode}', extra=msg_with_cid)

            if decoded_payload is None and 'decoded_payload' in uplink_message:
                lu.cid_logger.warning('Using decoded_payload from uplink_message', extra=msg_with_cid)
                decoded_payload = uplink_message['decoded_payload']

            if decoded_payload is not None:
                ts_vars = []
                for k, v in decoded_payload.items():
                    ts_vars.append({'name': k, 'value': v})

                p_ts_msg = {
                    BrokerConstants.CORRELATION_ID_KEY: correlation_id,
                    BrokerConstants.PHYSICAL_DEVICE_UID_KEY: pd.uid,
                    BrokerConstants.TIMESTAMP_KEY: received_at,
                    BrokerConstants.TIMESERIES_KEY: ts_vars
                }

                if _enabled_apps is None or app_id in _enabled_apps:
                    # Should the code try and remember the message until it is delivered to the queue?
                    # I think that means we need to hold off the ack in this method and only ack the message
                    # we got from ttn_raw when we get confirmation from the server that it has saved the message
                    # written to the physical_timeseries queue.
                    #lu.cid_logger.debug(f'Publishing to physical messages exchange: {json.dumps(p_ts_msg)}', extra=msg_with_cid)
                    msg_id = tx_channel.publish_message('physical_timeseries', p_ts_msg)
                else:
                    lu.cid_logger.debug(f'Not publishing from disabled app {app_id}.', extra=msg_with_cid)
            else:
                lu.cid_logger.warning(f'No payload could be decoded from message {correlation_id}', extra=msg_with_cid)
        else:
            lu.cid_logger.warning(f'No uplink_message in: {body}', extra=msg_with_cid)

        # This tells RabbitMQ the message is handled and can be deleted from the queue.    
        rx_channel._channel.basic_ack(delivery_tag)
        lu.cid_logger.debug('Acking message from ttn_raw.', extra=msg_with_cid)
    except dao.DAOException as e:
        logging.exception('Error while processing message.')
        rx_channel._channel.basic_reject(delivery_tag)


if __name__ == '__main__':
    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Does not return until SIGTERM is received.
    asyncio.run(main())
    logging.info('Exiting.')
