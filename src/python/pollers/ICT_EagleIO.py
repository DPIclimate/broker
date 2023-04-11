"""
This module is used to poll Arable weather data.

The date range can be specified.

Login is required using a username & password.

Since we're allowed to use the API as a customer, updates are at 15min intervals to ensure most recent data is available in storage end points such as Ubidots.

"""

import asyncio, datetime, dateutil.parser, hashlib, json, logging, os, pathlib, re, requests, signal, uuid
import util.LoggingUtil as lu
from glob import glob
import BrokerConstants
import api.client.DAO as dao
from pdmodels.Models import Location, PhysicalDevice
from pika.exchange_type import ExchangeType
import api.client.RabbitMQ as mq

_BASE_URL="https://api.eagle.io/api/v1/"

_eagleio_token = None
_eagleio_token = os.getenv("EAGLEIO_API_TOKEN")
_headers = {}

_poll_interval_seconds = 60 * 5

_sensor_group_response_hashes = {}

def poll() -> None:
    logging.info(f"Start polling EagleIO nodes.")

    if _eagleio_token is not None:
        _headers = {'x-api-key': f'{_eagleio_token}', 'Accept': 'application/json'}
        nodes = get_nodes(_headers)
        if nodes is not None:
            # Get a unique array of all nodes "name" values
            node_names = []
            # Create a list of all nodes with a class of "io.eagle.models.node.point.NumberPoint" (ie all sensors excluding unwanted data types i.e photos, etc).
            numberpoint_nodes = []
            for node in nodes:
                if node['_class'] == 'io.eagle.models.node.point.NumberPoint':
                    numberpoint_nodes.append(node)
                    # logging.info(f"Node Name: {node['name']}")
                    if node['name'].split(' ', 1)[0] not in node_names:
                        node_names.append(node['name'].split(' ', 1)[0])

            # Groups of values/variables for each Node "node_name".
            node_groups = []

            for node_name in node_names:
                node_feeds = []
                for node in numberpoint_nodes:
                    if node_name in node['name']:
                        node_feeds.append(node)
                node_groups.append(node_feeds)
            
            for node_name, node_sensors in zip(node_names, node_groups):
                process_sensor_node(node_name, node_sensors)
                # From here we now have grouped variables for each node. These also contain the most recent values for each variable and can thus be used to create new dots for each.
                # Now we should check the broker to see if each node already exists. If it does, we should update the last seen time and add the new values to the existing node.
                # If it doesn't exist, we should create a new node, update the last seen time, retrieve the historical data and add all values to it.

    else:
        logging.error(f"Error polling EagleIO: No API token available.")


# A sensor node is the same as a sensor group in this poller.
def process_sensor_node(node_name, node_sensors) -> None:
    global _sensor_group_response_hashes, tx_channel

    #
    # Check the hash of the current message against the hash of the previously
    # processed message. If they are the same then it is the same message and can
    # be ignored. If they are different then something has changed and the message
    # must be processed. Store the new hash when a different message arrives.
    #

    hash = hashlib.blake2b(json.dumps(node_sensors).encode()).hexdigest()
    logging.info(f"Message Hash: {hash}")
    sg_id_str = str(node_name)
    if sg_id_str in _sensor_group_response_hashes:
        if _sensor_group_response_hashes[sg_id_str] == hash:
            logging.info(f'Response for sensor group {sg_id_str} has not changed since the last poll.')
            return

    _sensor_group_response_hashes[sg_id_str] = hash

    # A magic date.
    max_ts = datetime.datetime(1972, 4, 9, tzinfo=datetime.timezone(datetime.timedelta(hours=10)))

    #
    # Find the latest timestamp for use
    # for the device last_seen value.
    #

    for sensor in node_sensors:
        ts_str = dateutil.parser.isoparse(f'{sensor["currentTime"]}')
        ts = dateutil.parser.isoparse(f'{ts_str}')
        if max_ts < ts:
            max_ts = ts
    
    logging.info(f"Sensor group {sg_id_str} last seen at {max_ts}.")

    #
    # Store the message in the raw messages table before doing any other processing.
    #

    correlation_id = str(uuid.uuid4())
    dao.add_raw_json_message(BrokerConstants.ICT_EAGLEIO, max_ts, correlation_id, node_sensors)
    msg_with_cid = {BrokerConstants.CORRELATION_ID_KEY: correlation_id, BrokerConstants.RAW_MESSAGE_KEY: node_sensors}

    #
    # Create the physical device if it does not exist, or update the last_seen time if it does.
    #

    source_ids = {
        BrokerConstants.SENSOR_GROUP_ID_KEY: node_name
    }

    pds = dao.get_pyhsical_devices_using_source_ids(BrokerConstants.ICT_EAGLEIO, source_ids)
    if len(pds) < 1:
        lu.cid_logger.info(f'Physical device not found for sensor group {node_name}, creating a new one.', extra=msg_with_cid)

        # Add this in for context, but it is not used by the query above
        # so it has to be put in later (ie now).
        #source_ids['location_name'] = location['name']

        props = {
            BrokerConstants.ICT_EAGLEIO: node_sensors,
            BrokerConstants.CREATION_CORRELATION_ID_KEY: correlation_id,
            BrokerConstants.LAST_MESSAGE_HASH_KEY: hash
        }

        # Consider adding loop to retrieve all historical data for node and process it as well.

        pd = PhysicalDevice(source_name=BrokerConstants.ICT_EAGLEIO, name=node_name, location=None, last_seen=max_ts, source_ids=source_ids, properties=props)
        pd = dao.create_physical_device(pd)
    else:
        lu.cid_logger.info(f'Accepted message from {node_name}, updating last seen time to {max_ts}.', extra=msg_with_cid)
        pd = pds[0]
        pd.last_seen = max_ts
        pd.properties[BrokerConstants.LAST_MESSAGE_HASH_KEY] = hash
        pd = dao.update_physical_device(pd)


    #
    # Publish a message to the physical_timeseries queue.
    #
    # Assume most sensor readings will have a timestamp of max_ts so use that as the
    # default timestamp in the physical_timeseries message. Only set a timestamp on
    # a sensor reading if it is different to max_ts. This can happen if 1 sensor has 
    # stopped reporting or has been disconnected and the other sensors are still 
    # reporting which can lead to a different hash.
    #

    """
    {
        "broker_correlation_id": "f0200e8b-9250-4812-9742-13dda8d1afca",
        "p_uid": 232,
        "timestamp": "2022-02-11T00:18:29.917095010Z",
        "timeseries": [
            {"name": "battery", "value": 3.1},
            {"name": "mm", "value": 5, "timestamp": "2022-02-10T23:18:29.23Z"}
        ]
    }
    """

    dots = []
    for sensor in node_sensors:
        dot = { # Replace the variable/dot name with the node name removed.
            'name': sensor['name'].replace(f'{node_name} ', ''),
            'value': sensor['currentValue']
        }

        dot_ts = dateutil.parser.isoparse(f'{sensor["currentTime"]}')
        if dot_ts != max_ts:
            dot[BrokerConstants.TIMESTAMP_KEY] = dot_ts.isoformat()

        dots.append(dot)
    
    p_ts_msg = {
        BrokerConstants.CORRELATION_ID_KEY: correlation_id,
        BrokerConstants.PHYSICAL_DEVICE_UID_KEY: pd.uid,
        BrokerConstants.TIMESTAMP_KEY: max_ts.isoformat(),
        BrokerConstants.TIMESERIES_KEY: dots
    }

    lu.cid_logger.info(f'Publishing message for {node_name}: {p_ts_msg}.', extra=msg_with_cid)

    msg_id = tx_channel.publish_message('physical_timeseries', p_ts_msg)


finish = False
tx_channel = None
mq_client = None


def get_nodes(_headers) -> None:
    url = f"{_BASE_URL}nodes"
    logging.info(f"Requesting EagleIO nodes from {url}...")
    try:
        request = requests.get(url, headers=_headers, timeout=10)
    except Exception as e:
        request = None
        logging.error(f"Request timeout getting EagleIO nodes. \n{e}")

    if request is not None:
        if request.status_code == 200:
            logging.info(f"Got EagleIO nodes.")
            nodes = request.json()
            return nodes
        else:
            logging.error(f"Error getting EagleIO nodes: {request.status_code} {request.text}")
            return None
    else:
        return None


def initialise_message_hashes() -> None:
    global _sensor_group_response_hashes

    devs = dao.get_physical_devices({'source': BrokerConstants.ICT_EAGLEIO})
    for pd in devs:
        if BrokerConstants.LAST_MESSAGE_HASH_KEY in pd.properties:
            sg_id_str = str(pd.source_ids[BrokerConstants.SENSOR_GROUP_ID_KEY])
            hash = pd.properties[BrokerConstants.LAST_MESSAGE_HASH_KEY]
            _sensor_group_response_hashes[sg_id_str] = hash


def sigterm_handler(sig_no, stack_frame) -> None:
    """
    Handle SIGTERM from docker by closing the mq and db connections and setting a
    flag to tell the main loop to exit.
    """
    global finish, mq_client

    logging.info(f'{signal.strsignal(sig_no)}, setting finish to True')
    finish = True
    dao.stop()
    mq_client.stop()


async def publish_ack(delivery_tag: int) -> None:
    pass

async def start_mq() -> None:
    global mq_client, tx_channel

    tx_channel = mq.TxChannel(exchange_name=BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME, exchange_type=ExchangeType.fanout)
    mq_client = mq.RabbitMQConnection(channels=[tx_channel])
    asyncio.create_task(mq_client.connect())

    # Wait for the RabbitMQ connection & channel to be ready to use.
    # asyncio.sleep(0) is supposed to be a special case that allows
    # control to be passed back to the asyncio event loop quickly.
    while not tx_channel.is_open:
        await asyncio.sleep(0)

async def main():
    global mq_client, finish

    logging.info('===============================================================')
    logging.info('                  STARTING Eagle.IO POLLER')
    logging.info('===============================================================')

    await start_mq()

    initialise_message_hashes()

    while not finish:
        poll()
        # Smallest report period for a sensor is 15mins. Polling every 5 mins should be sufficient to allow for 1 missed poll.
        await asyncio.sleep(_poll_interval_seconds)

    while not mq_client.stopped:
        await asyncio.sleep(1)

if __name__ == '__main__':

    if _eagleio_token is not None:
        # Docker sends SIGTERM to tell the process the container is stopping so set
        # a handler to catch the signal and initiate an orderly shutdown.
        signal.signal(signal.SIGTERM, sigterm_handler)

        # Does not return until SIGTERM is received.
        asyncio.run(main())
        logging.info('Exiting.')

