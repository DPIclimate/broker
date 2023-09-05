import sys, json, re, os, logging, psycopg2
import BrokerConstants
import api.client.DAO as dao
import util.LoggingUtil as lu
from dateutil import parser
from util import NamingConstants


#these are read from compose/.env file
#however tsdb sets them from compose/.tsdb_env
tsdb_user  = os.environ.get("TSDB_USER")
tsdb_pass  = os.environ.get("TSDB_PASSWORD")
tsdb_host  = os.environ.get("TSDB_HOST")
tsdb_port  = os.environ.get("TSDB_PORT")
tsdb_db    = os.environ.get("TSDB_DB")
tsdb_table = os.environ.get("TSDB_TABLE")
CONNECTION = f"postgres://{tsdb_user}:{tsdb_pass}@{tsdb_host}:{tsdb_port}/{tsdb_db}"


def get_standardised_name(msg: str) -> str:
    """
    check if a name is already mapped and use that format instead,
    otherwise lets create a new mapping and use it
    """
    std_name = dao.get_std_name(msg)
    if std_name is None:
        std_name = NamingConstants.clean_name(msg)
        dao.add_name_map(msg, std_name)
        logging.info(f'Creating New Name Mapping: {msg}:{std_name}')
    else:
        logging.info(f'Found Name Mapping: {msg}:{std_name}')

    return std_name


def parse_json(json_obj: dict) -> list:
    """
    Main parser used at this time, takes a json object and parses into format ready for insertion into tsdb
    """
    parsed_data = []

    try:
        broker_id = json_obj[BrokerConstants.CORRELATION_ID_KEY]
        l_uid = json_obj[BrokerConstants.LOGICAL_DEVICE_UID_KEY]
        p_uid = json_obj[BrokerConstants.PHYSICAL_DEVICE_UID_KEY]
        timestamp = parser.parse(json_obj[BrokerConstants.TIMESTAMP_KEY])
        timeseries = json_obj[BrokerConstants.TIMESERIES_KEY]

        for tsd in timeseries:
            name = get_standardised_name(tsd['name'])
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
    """
    Insert our parsed data into tsdb

    returns 1 if an error occurred
    returns 0 if sucessful
    """
    conn = psycopg2.connect(connection)
    cursor = conn.cursor()
    try:
        for entry in parsed_data:
            broker_id, l_uid, p_uid, timestamp, name, value = entry
            cursor.execute(
                ## maybe we should update table to use correlation id key
                f"INSERT INTO {table} (broker_id,{BrokerConstants.LOGICAL_DEVICE_UID_KEY}, {BrokerConstants.PHYSICAL_DEVICE_UID_KEY}, {BrokerConstants.TIMESTAMP_KEY}, name, value) VALUES (%s, %s, %s, %s, %s, %s);",
                (broker_id, l_uid, p_uid, timestamp, name, value))
    except (Exception, psycopg2.Error) as error:
        print(error)
        return 0
    conn.commit()
    cursor.close
    return 1
