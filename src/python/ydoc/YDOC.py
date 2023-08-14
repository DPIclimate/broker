import datetime, dateutil.parser

import asyncio, json, logging, re, signal, sys, uuid
from typing import Dict, Optional

import BrokerConstants
from pdmodels.Models import PhysicalDevice
from pika.exchange_type import ExchangeType

import api.client.RabbitMQ as mq
import api.client.TTNAPI as ttn

import api.client.DAO as dao

import util.LoggingUtil as lu
import util.Timestamps as ts

# Prometheus metrics
from prometheus_client import Counter, start_http_server
request_counter = Counter('requests_total', 'Total Requests')
failed_messages_counter = Counter('failed_messages_total', 'Total Failed Messages')
new_devices_counter = Counter('new_devices_total', 'Total New Devices Detected')
existing_devices_messages_counter = Counter('existing_devices_messages_total', 'Total Messages from Existing Devices')
dropped_messages_counter = Counter('dropped_messages_total', 'Total Dropped Messages')
published_messages_counter = Counter('published_messages_total', 'Total Published Messages')
failed_published_messages_counter = Counter('failed_published_messages_total', 'Total Failed Published Messages')
errors_counter = Counter('errors_total', 'Total Errors Encountered')
active_connections_gauge = Counter('active_connections', 'Number of Active RabbitMQ Connections')

# Start up the server to expose the metrics.
start_http_server(8003)

std_logger = logging.getLogger(__name__)

rx_channel: mq.RxChannel = None
tx_channel: mq.TxChannel = None
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

    # The default MQTT topic of YDOC devices is YDOC/<serial#> which RabbitMQ converts into a routing key of YDOC.<serial#>.
    # It seems we can use the MQTT topic wildcard of # to get all YDOC messages.
    rx_channel = mq.RxChannel('amq.topic', exchange_type=ExchangeType.topic, queue_name='ydoc_listener',
                              on_message=on_message, routing_key='YDOC.#')
    tx_channel = mq.TxChannel(exchange_name=BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME,
                              exchange_type=ExchangeType.fanout)
    mq_client = mq.RabbitMQConnection(channels=[rx_channel, tx_channel])
    asyncio.create_task(mq_client.connect())
    active_connections_gauge.inc()

    # while not (rx_channel.is_open and tx_channel.is_open):
    while not (rx_channel.is_open):
        await asyncio.sleep(0)

    while not finish:
        await asyncio.sleep(2)

    while not mq_client.stopped:
        await asyncio.sleep(1)

    active_connections_gauge.dec()

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


# This re is used to get the sensor # and reading name prefix from the YDOC json.
# The YDOC may send upper or lower case so the code lower-cases the string before
# this re is used.
# The sensor # determines the physical device, and the reading name prefix is used
# to make the reading names unique when multiple sensors of the same type are
# connected to the YDOC, such as 2 enviopros. The reading name prefix is stripped
# off the reading name before it is added to a physical timeseries message.
_sensor_code_re = re.compile(r'^([a-z]\d+)([a-z]\d+)')

_non_alpha_numeric = re.compile(r'\W')


def process_message(msg_with_cid: Dict) -> Dict[str, Dict]:
    # Create a map of the channel objects keyed by channel code to make it simple
    # to find the variable name, uom, etc while processing values.
    channels = {}
    msg = msg_with_cid[BrokerConstants.RAW_MESSAGE_KEY]

    for c in msg['channels']:
        if 'code' in c:
            channels[c['code'].lower()] = c

    last_seen = None
    serial_no = msg['device']['sn']
    dev_name = msg['device']['name']
    data = msg['data']

    devices = {}

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
            # The channel codes are converted to lower-case because we've decided to standardise
            # on that.
            k = k.lower()
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
                lu.cid_logger.debug(f'Skipping key {k}', extra=msg_with_cid)
                continue

            sc_match = _sensor_code_re.match(k)
            if sc_match is None:
                # If the channel id does not match our convention of s<n>... then assume it is a node
                # level value such as voltage or processor temperature.
                channel = channels[k]
                lu.cid_logger.debug(f'YDOC node level data : ({k}) {channel["name"]} = {v} {channel["unit"]}',
                                    extra=msg_with_cid)
                dev_id = f'ydoc-{serial_no}'
                logical_dev_name = f'{dev_name.strip()} ({dev_id})'
                # Set a prefix that cannot be matched down where the var_name is set so that the node
                # level vars will get the proper names.
                s_prefix = '!'
            else:
                sc_groups = sc_match.groups()
                s_prefix = sc_groups[0]
                dev_id = f'{serial_no}-{s_prefix}'
                logical_dev_name = f'{dev_name.strip()} ({s_prefix})'

            if dev_id not in devices:
                devices[dev_id] = {
                    'id': dev_id,
                    'name': logical_dev_name,
                    'dots': []
                }

            device = devices[dev_id]

            channel_name: str = channels[k]['name']
            var_name = channel_name[2:] if channel_name.startswith(s_prefix) else _non_alpha_numeric.sub('_',
                                                                                                         channel_name)

            try:
                dot = {BrokerConstants.TIMESTAMP_KEY: ts, 'name': var_name, 'value': float(v)}
                device['dots'].append(dot)
            except:
                lu.cid_logger.info(f'YDOC variable {var_name} nan, got {v} instead.', extra=msg_with_cid)

    return devices


def on_message(channel, method, properties, body):
    """
    This function is called when a message arrives from RabbitMQ.
    """
    global rx_channel, tx_channel, finish

    delivery_tag = method.delivery_tag
    request_counter.inc()

    # If the finish flag is set, reject the message so RabbitMQ will re-queue it
    # and return early.
    if finish:
        rx_channel._channel.basic_reject(delivery_tag)
        return

    if body[0] != 123 or body[1] != 34:
        std_logger.info(f'Ignoring non-JSON message: {body}')
        dropped_messages_counter.inc()
        rx_channel._channel.basic_ack(delivery_tag)
        return

    try:
        """
        {"device":{"sn":108173526,"name":"Elephant Yards Pond 3 ","v":"4.4B6","imei":352909081735264,"sim":89882280666027703499},
        "channels":[
        {"code":"S1M1","name":"s1moisture1","unit":""},
        {"code":"S1T1","name":"s1temperature1","unit":""},
        {"code":"SB","name":"Signal","unit":"bars"},
        {"code":"SDB","name":"Signal strength","unit":"dBm"},
        {"code":"AVGVi","name":"Average voltage","unit":"V"},
        {"code":"S1T2","name":"s1temperature2","unit":""},
        {"code":"S1T3","name":"s1temperature3","unit":""},
        {"code":"S1T4","name":"s1temperature4","unit":""},
        {"code":"S1S1","name":"s1salinity1","unit":""},
        {"code":"S1S2","name":"s1salinity2","unit":""},
        {"code":"S1M2","name":"s1moisture2","unit":""},
        {"code":"S1M3","name":"s1moisture3","unit":""},
        {"code":"S1M4","name":"s1moisture4","unit":""},
        {"code":"S1S3","name":"s1salinity3","unit":""},
        {"code":"S1S4","name":"s1salinity4","unit":""},
        {"code":"S2M1","name":"s2moisture1","unit":""},
        {"code":"S2M2","name":"s2moisture2","unit":""},
        {"code":"S2M3","name":"s2moisture3","unit":""},
        {"code":"S2M4","name":"s2moisture4","unit":""},
        {"code":"S2S1","name":"s2salinity1","unit":""},
        {"code":"S2T1","name":"s2temperature1","unit":""},
        {"code":"S2T2","name":"s2temperature2","unit":""},
        {"code":"S2T3","name":"s2temperature3","unit":""},
        {"code":"S2T4","name":"s2temperature4","unit":""},
        {"code":"S2S2","name":"s2salinity2","unit":""},
        {"code":"S2S3","name":"s2salinity3","unit":""},
        {"code":"S2S4","name":"s2salinity4","unit":""},
        {}],
        "data":[
        {"$ts":220317121510,"S1M1":5.84,"S1T1":20.25,"AVGVi":3.32,"S1T2":20.29,"S1T3":20.39,"S1T4":20.46,"S1S1":0,"S1S2":0,"S1M2":8.3,"S1M3":5.25,"S1M4":7.52,"S1S3":0,"S1S4":0,"S2M1":11.26,"S2M2":12.3,"S2M3":6.64,"S2M4":6.17,"S2S1":0,"S2T1":20.49,"S2T2":20.68,"S2T3":20.55,"S2T4":20.4,"S2S2":0,"S2S3":0,"S2S4":0},
        {}]}

        Notes.

        1. The ydoc firmware requires the channel names to be distinct so we can't name them temperature1, temperature2 etc.
           To split the different sensors out into different physical devices, these unique names must be mapped onto more
           generic names.

           This will be done by convention. The channel codes must be s<a>t<b>, eg s1t2, where s1 is used to determine the
           physical device the channel belongs to. That same prefix is expected to be on the channel name, and stripping
           it from there will provide the variable name.
        """
        # The message from the webhook process already has the correlation id in it.
        correlation_id = str(uuid.uuid4())
        lu.cid_logger.info(f'Message as received: {body}', extra={BrokerConstants.CORRELATION_ID_KEY: correlation_id})

        msg = {}
        try:
            msg = json.loads(body)
        except Exception as e:
            std_logger.info(f'JSON parsing failed, ignoring message')
            failed_messages_counter.inc()
            rx_channel._channel.basic_ack(delivery_tag)
            return

        msg_with_cid = {BrokerConstants.CORRELATION_ID_KEY: correlation_id, BrokerConstants.RAW_MESSAGE_KEY: msg}

        # Record the message to the all messages table before doing anything else to ensure it
        # is saved. Attempts to add duplicate messages are ignored in the DAO.
        # The 'now' timestamp is used so the message can be recorded ASAP and before any processing
        # that might fail or cause the message to be ignored is performed.
        dao.add_raw_json_message(BrokerConstants.YDOC, ts.now_utc(), correlation_id, msg)

        if 'data' not in msg:
            lu.cid_logger.info(f'Ignoring message because it has no data element.', extra=msg_with_cid)
            rx_channel._channel.basic_ack(delivery_tag)
            return

        serial_no = msg['device']['sn']
        dev_name = msg['device']['name']

        lu.cid_logger.info(f'Accepted message from {dev_name} {serial_no}', extra=msg_with_cid)

        printed_msg = False
        devices = process_message(msg_with_cid)
        lu.cid_logger.info(f'Processed message {dev_name} {serial_no}', extra=msg_with_cid)
        lu.cid_logger.info(devices, extra=msg_with_cid)
        for device in devices.values():
            source_ids = {
                'id': device['id']
            }

            if len(device['dots']) > 0:
                max_ts_dot = max(device['dots'], key=lambda d: dateutil.parser.parse(d[BrokerConstants.TIMESTAMP_KEY]))
                last_seen = max_ts_dot[BrokerConstants.TIMESTAMP_KEY]
            else:
                continue

            pds = dao.get_pyhsical_devices_using_source_ids(BrokerConstants.YDOC, source_ids)
            if len(pds) < 1:
                new_devices_counter.inc()
                if not printed_msg:
                    printed_msg = True
                    lu.cid_logger.info(f'Message from a new device.', extra=msg_with_cid)
                    lu.cid_logger.info(body, extra=msg_with_cid)

                lu.cid_logger.info('Device not found, creating physical device.', extra=msg_with_cid)

                props = {
                    BrokerConstants.YDOC: msg,
                    BrokerConstants.CREATION_CORRELATION_ID_KEY: correlation_id,
                    BrokerConstants.LAST_MSG: msg
                }

                pd = PhysicalDevice(source_name=BrokerConstants.YDOC, name=device['name'], location=None,
                                    last_seen=last_seen, source_ids=source_ids, properties=props)
                pd = dao.create_physical_device(pd)
            else:
                existing_devices_messages_counter.inc()
                pd = pds[0]
                if last_seen is not None:
                    pd.last_seen = last_seen
                    pd.properties[BrokerConstants.LAST_MSG] = msg
                    pd = dao.update_physical_device(pd)

            if pd is None:
                lu.cid_logger.error(f'Physical device not found, message processing ends now. {correlation_id}',
                                    extra=msg_with_cid)
                rx_channel._channel.basic_ack(delivery_tag)
                return

            min_ts_dot = min(device['dots'], key=lambda d: dateutil.parser.parse(d[BrokerConstants.TIMESTAMP_KEY]))
            lu.cid_logger.debug(f'From {device["dots"]}, min_ts is {min_ts_dot}', extra=msg_with_cid)

            p_ts_msg = {
                BrokerConstants.CORRELATION_ID_KEY: correlation_id,
                BrokerConstants.PHYSICAL_DEVICE_UID_KEY: pd.uid,
                BrokerConstants.TIMESTAMP_KEY: min_ts_dot[BrokerConstants.TIMESTAMP_KEY],
                BrokerConstants.TIMESERIES_KEY: device['dots']
            }

            lu.cid_logger.debug(f'Publishing message: {p_ts_msg}', extra=msg_with_cid)
            try:
                tx_channel.publish_message('physical_timeseries', p_ts_msg)
                published_messages_counter.inc()
            except:
                failed_published_messages_counter.inc()
                lu.cid_logger.error('Failed to publish message to RabbitMQ.', extra=msg_with_cid)

        # This tells RabbitMQ the message is handled and can be deleted from the queue.    
        rx_channel._channel.basic_ack(delivery_tag)
        published_messages_counter.inc()
        lu.cid_logger.debug('Acking message from ttn_raw.', extra=msg_with_cid)
    except Exception as e:
        std_logger.exception('Error while processing message.')
        errors_counter.inc()
        rx_channel._channel.basic_ack(delivery_tag)


if __name__ == '__main__':
    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)

    if len(sys.argv) > 1:
        for filename in sys.argv[1:]:
            with open(filename, mode='r') as file:
                correlation_id = str(uuid.uuid4())
                msg = json.load(file)
                msg_with_cid = {BrokerConstants.CORRELATION_ID_KEY: correlation_id,
                                BrokerConstants.RAW_MESSAGE_KEY: msg}
                devices = process_message(msg_with_cid)
                print(json.dumps(devices, indent=2))
                print('')
    else:
        # Does not return until SIGTERM is received.
        asyncio.run(main())
        logging.info('Exiting.')
