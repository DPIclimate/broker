"""
This should be a module that is loaded by the polled services driver.

It can specify it's period, have an init function and an execute (or poll) function.

1. Login to get token.
2. Use bootstrap to get a list of sites/stations/sensor-groups. The sensor-groups are the
   entities used in the polling - each one polled separately.

3. Do an hourly poll, preferably a few minutes past the hour. Green Brain seems to report
   hourly, on the hour.

   Keep the most recent poll response hash in the physical device properties so we can see
   which values are new. Every 'dot' from Green Brain has its own timestamp and not all
   of them are the same - for instance the logger status values can fall behind, so using
   timestamps is difficult.

   Perhaps we need to keep the entire most recent response so if the hashes do differ we
   can still analyse which readings have changed and not send on the ones that haven't. There
   are examples of some sensors last being seen months ago but they keep showing up in the
   'latest' responses because those are the latest readings from those sensors. So some parts
   of a station or sensor group might keep moving on and others get stuck in the past but still
   get included in every response.

TODO: Abstract out some common patterns these services have into classes that can either be
      extended from or composed with.
"""
import asyncio, datetime, dateutil.parser, hashlib, json, logging, os, pathlib, re, requests, signal, uuid
from glob import glob
import BrokerConstants
import db.DAO as dao
from pdmodels.Models import Location, PhysicalDevice
from pika.exchange_type import ExchangeType
import api.client.RabbitMQ as mq


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
logger = logging.getLogger(__name__)

_users = os.environ['GREENBRAIN_USERS'].split(',')
_passwords = os.environ['GREENBRAIN_PASSWORDS'].split(',')

_accounts = {}

_BASE_URL='https://api.greenbrain.net.au/v3'

_ts_regex = re.compile(r'"time":"(\d\d\d\d-\d\d-\d\dT\d\d[\d:.]+?\d)"')


# Store a hash of the response content of the previous 'latest values' message
# for each sensor group. If we get the same hash value from the response to
# the next poll we know nothing has changed. We avoid having to check every
# timestamp in the response by using the hash of the entire response.
#
# This does mean we need to remember the last response between runs
# so we don't re-process a response after a restart. We should probably
# store the most recent hash value in the physical device properties and
# live with the small chance of the occasional double entry in raw_messages
# if we crash between doing a poll and writing the hash to the physical_devices
# table.
_sensor_group_reponse_hashes = {}

def download_bootstrap_info():
    global _accounts
    cached = False
    b_json = pathlib.Path('b.json')
    if b_json.exists() and b_json.is_file():
        logger.info(f'Loading cached info from {str(b_json)}')
        with open(b_json, 'r') as f:
            _accounts = json.load(f)
        cached = True

    url = f'{_BASE_URL}/auth/login'
    for user, password in zip(_users, _passwords):
        logger.info(f'Authenticating user {user}')
        if user not in _accounts:
            _accounts[user] = {}

        r = requests.post(url, json={'username': user, 'password': password})
        if r.status_code == 200:
            body_obj = r.json()
            _accounts[user]['auth'] = body_obj
        else:
            raise r

    if cached:
        return
    
    for username, account in _accounts.items():
        logger.info(f'Downloading info for user {username}')
        token = account['auth']['token']
        h = {'Authorization': f'bearer {token}', 'Accept': 'application/json'}

        # The bootstrap call returns all the station and device information for
        # the account. This is where the physical devices will be found.
        logger.info('bootstrap')
        r = requests.get(f'{_BASE_URL}/bootstrap', headers=h)
        if r.status_code == 200:
            account['bootstrap'] = r.json()
        else:
            raise r

        #
        # FROM HERE DOWN MIGHT NOT BE NECESSARY.
        #

        # The -types and -models API calls provide descriptive information
        # for the various ids that are returned in the bootstrap object,
        # like lookup tables in a database.
        logger.info('station-types')
        r = requests.get(f'{_BASE_URL}/station-types', headers=h)
        if r.status_code == 200:
            account['station_types'] = {}
            st_list = r.json()
            for entry in st_list:
                account['station_types'][entry['id']] = entry

        else:
            raise r

        logger.info('sensor-group-types')
        r = requests.get(f'{_BASE_URL}/sensor-group-types', headers=h)
        if r.status_code == 200:
            sgt_list = r.json()
            account['sensor_group_types'] = {}
            for entry in sgt_list:
                account['sensor_group_types'][entry['id']] = entry
        else:
            raise r

        logger.info('sensor-group-models')
        r = requests.get(f'{_BASE_URL}/sensor-group-models', headers=h)
        if r.status_code == 200:
            account['sensor_group_models'] = {}
            sgm_list = r.json()
            for entry in sgm_list:
                account['sensor_group_models'][entry['id']] = entry
        else:
            raise r

        logger.info('sensor-types')
        r = requests.get(f'{_BASE_URL}/sensor-types', headers=h)
        if r.status_code == 200:
            account['sensor_types'] = {}
            stp_list = r.json()
            for entry in stp_list:
                account['sensor_types'][entry['id']] = entry
        else:
            raise r

        logger.info('Saving downloaded information.')
        with open("a.json", 'w') as f:
            json.dump(_accounts, f)


def initialise_message_hashes() -> None:
    global _sensor_group_reponse_hashes

    devs = dao.get_physical_devices({'source': BrokerConstants.GREENBRAIN})
    for pd in devs:
        if BrokerConstants.LAST_MESSAGE_HASH_KEY in pd.properties:
            sg_id_str = str(pd.source_ids[BrokerConstants.SENSOR_GROUP_ID_KEY])
            hash = pd.properties[BrokerConstants.LAST_MESSAGE_HASH_KEY]
            _sensor_group_reponse_hashes[sg_id_str] = hash


def poll() -> None:
    logger.info('Start of poll cycle')
    for account in _accounts.values():              # Green Brain account level, eg a.b@xyz.com
        token = account['auth']['token']
        h = {'Authorization': f'bearer {token}', 'Accept': 'application/json'}
        bootstrap = account['bootstrap']
        for system in bootstrap['systems']:         # Systems are sites, such as Griffith Research Station.
            logger.info(f'System: {system["name"]}')
            for station in system['stations']:      # Stations are data logging nodes such as an ICT node.
                logger.info(f'Station: {station["name"]}')
                for sg in station['sensorGroups']:  # Sensor groups are devices attached to stations, eg an env pro
                    sg_id = sg['id']
                    logger.info(f'Sensor group: {sg_id}: {sg["name"]}')
                    r = requests.get(f'{_BASE_URL}/sensor-groups/{sg_id}/latest', headers=h)
                    if r.status_code == 200:
                        process_sensor_group(station, sg_id, r.text, r.json())
                    else:
                        logger.error(r)

                # Return early while testing, just do one station.
                return


# Passing in as text so we can use regexps to quickly find some things.
def process_sensor_group(station, sensor_group_id, text, json_obj) -> None:
    global _sensor_group_reponse_hashes, tx_channel

    #
    # Check the hash of the current message against the hash of the previously
    # processed message. If they are the same then it is the same message and can
    # be ignored. If they are different then something has changed and the message
    # must be processed. Store the new hash when a different message arrives.
    #

    hash = hashlib.blake2b(text.encode()).hexdigest()
    sg_id_str = str(sensor_group_id)
    if sg_id_str in _sensor_group_reponse_hashes:
        if _sensor_group_reponse_hashes[sg_id_str] == hash:
            logger.info(f'Response for sensor group {sg_id_str} has not changed since the last poll.')
            return

    _sensor_group_reponse_hashes[sg_id_str] = hash

    # A magic date.
    max_ts = datetime.datetime(1972, 4, 9, tzinfo=datetime.timezone(datetime.timedelta(hours=10)))

    #
    # Each sensor reading within the group has its own timestamp and for some sensor types
    # they can be different within the same message, so find the latest timestamp for use
    # as the device last_seen value.
    #

    for match in _ts_regex.finditer(text):
        ts_str = match.group(1)
        ts = dateutil.parser.isoparse(f'{ts_str}Z')
        if max_ts < ts:
            max_ts = ts

    #
    # Store the message in the raw messages table before doing any other processing.
    #

    correlation_id = str(uuid.uuid4())
    dao.add_raw_json_message(BrokerConstants.GREENBRAIN, max_ts, correlation_id, json_obj)

    #
    # Create the physical device if it does not exist, or update the last_seen time if it does.
    #

    source_ids = {
        BrokerConstants.SENSOR_GROUP_ID_KEY: sensor_group_id
    }

    pd = dao.get_pyhsical_device_using_source_ids(BrokerConstants.GREENBRAIN, source_ids)
    if pd is None:
        logger.info(f'Physical device not found for sensor group {sensor_group_id}, creating a new one.')
        name = json_obj['sensorGroup']['name']
        
        try:
            location = Location(lat=float(station['latitude']), long=float(station['longitude']))
        except:
            location = None

        # Add this in for context, but it is not used by the query above
        # so it has to be put in later (ie now).
        source_ids['system_id'] = station['systemId']
        source_ids['station_id'] = station['id']
        source_ids['station_name'] = station['name']

        props = {
            BrokerConstants.GREENBRAIN: json_obj,
            BrokerConstants.CREATION_CORRELATION_ID_KEY: correlation_id,
            BrokerConstants.LAST_MESSAGE_HASH_KEY: hash
        }

        pd = PhysicalDevice(source_name=BrokerConstants.GREENBRAIN, name=name, location=location, last_seen=max_ts, source_ids=source_ids, properties=props)
        pd = dao.create_physical_device(pd)
    else:
        pd.last_seen = max_ts
        pd.properties[BrokerConstants.LAST_MESSAGE_HASH_KEY] = hash
        pd = dao.update_physical_device(pd)

    #
    # Publish a message to the physical_timeseries queue.
    #
    # Assume most sensor readings will have a timestamp of max_ts so use that as the
    # default timestamp in the physical_timeseries message. Only set a timestamp on
    # a sensor reading if it is different to max_ts.
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
    for sensor_type in json_obj['sensorTypes'].values():
        for sensor in sensor_type['sensors']:
            dot = {
                'name': sensor['name'],
                'value': sensor['value']
            }

            dot_ts = dateutil.parser.isoparse(f'''{sensor['time']}Z''')
            if dot_ts != max_ts:
                dot[BrokerConstants.TIMESTAMP_KEY] = dot_ts.isoformat()

            dots.append(dot)
    
    p_ts_msg = {
        BrokerConstants.CORRELATION_ID_KEY: correlation_id,
        BrokerConstants.PHYSICAL_DEVICE_UID_KEY: pd.uid,
        BrokerConstants.TIMESTAMP_KEY: max_ts.isoformat(),
        BrokerConstants.TIMESERIES_KEY: dots
    }

    # Should the code try and remember the message until it is delivered to the queue?
    # I think that means we need to hold off the ack in this method and only ack the message
    # we got from ttn_raw when we get confirmation from the server that it has saved the message
    # written to the physical_timeseries queue.
    msg_id = tx_channel.publish_message('physical_timeseries', p_ts_msg)


finish = False
tx_channel = None
mq_client = None


def sigterm_handler(sig_no, stack_frame) -> None:
    """
    Handle SIGTERM from docker by closing the mq and db connections and setting a
    flag to tell the main loop to exit.
    """
    global finish, mq_client

    logger.info(f'{signal.strsignal(sig_no)}, setting finish to True')
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

    logger.info('===============================================================')
    logger.info('               STARTING GREENBRAIN POLLER')
    logger.info('===============================================================')

    await start_mq()

    download_bootstrap_info()
    initialise_message_hashes()

    while not finish:
        poll()
        await asyncio.sleep(60 * 30)

    while not mq_client.stopped:
        await asyncio.sleep(1)


if __name__ == '__main__':
    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Does not return until SIGTERM is received.
    asyncio.run(main())
    logger.info('Exiting.')
