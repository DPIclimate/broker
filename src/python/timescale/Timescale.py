import sys, json, re, os, logging, psycopg2
import BrokerConstants
import api.client.DAO as dao
import util.LoggingUtil as lu
from dateutil import parser

#these are read from compose/.env file
#however tsdb sets them from compose/.tsdb_env
tsdb_user  = os.environ.get("TSDB_USER")
tsdb_pass  = os.environ.get("TSDB_PASSWORD")
tsdb_host  = os.environ.get("TSDB_HOST")
tsdb_port  = os.environ.get("TSDB_PORT")
tsdb_db    = os.environ.get("TSDB_DB")
tsdb_table = os.environ.get("TSDB_TABLE")
CONNECTION = f"postgres://{tsdb_user}:{tsdb_pass}@{tsdb_host}:{tsdb_port}/{tsdb_db}"


def clean_names(msg: str) -> str:
    """
    strip special chars from beginning and end
    make upper case
    replace _ with <space>
    remove special characters
    remove duplicated '_'

    it does not expand or compress things like voltage
    """
    special_characters = '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ '
    ret = msg.lstrip(special_characters).rstrip(special_characters)
    ret = ret.upper().replace(" ", "_").replace("-","_")
    ret = re.sub(r'[^\w\s]', '', ret)
    ret = re.sub(r'_+', '_', ret)

    return ret


def get_standardised_name(msg: str) -> str:
    std_name = dao.get_std_name(msg)
    if std_name is None:
        std_name = clean_names(msg)
        lu.cid_logger.info(f'Creating New Name Mapping: {msg}:{std_name}')
    else:
        lu.cid_logger.info(f'Found Name Mapping: {msg}:{std_name}')

    return std_name


def parse_json(json_obj: dict) -> list:
    """
    Main parser used at this time, takes a json.loads object.
    """
    parsed_data = []

    try:
        broker_id = json_obj[BrokerConstants.CORRELATION_ID_KEY]
        l_uid = json_obj[BrokerConstants.LOGICAL_DEVICE_UID_KEY]
        p_uid = json_obj[BrokerConstants.PHYSICAL_DEVICE_UID_KEY]
        timestamp = parser.parse(json_obj[BrokerConstants.TIMESTAMP_KEY])
        timeseries = json_obj[BrokerConstants.TIMESERIES_KEY]

        for tsd in timeseries:
            name = tsd['name']
            value = tsd['value']
            parsed_data.append((broker_id, l_uid, p_uid, timestamp, name, value))

    except KeyError as e:
        logging.error(f"An error occurred: {str(e)}")

    return parsed_data


def parse_json_string(json_string: str) -> list:
    """
    Alternative to above, includes json.loads prior.
    """
    parsed_data = []
    try:
        parsed_data.append(parse_json(json.loads(json_string)))
    except json.JSONDecodeError as e:
        logging.error(f"An error occurred: {str(e)}")

    return parsed_data


def insert_lines(parsed_data: list, connection: str = CONNECTION, table: str = tsdb_table) -> int:
    conn = psycopg2.connect(connection)
    cursor = conn.cursor()
    try:
        for entry in parsed_data:
            broker_id, l_uid, p_uid, timestamp, name, value = entry
            cursor.execute(
                f"INSERT INTO {table} (broker_id, l_uid, p_uid, timestamp, name, value) VALUES (%s, %s, %s, %s, %s, %s);",
                (broker_id, l_uid, p_uid, timestamp, name, value))
    except (Exception, psycopg2.Error) as error:
        print(error)
        return 0
    conn.commit()
    cursor.close
    return 1
