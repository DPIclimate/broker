import psycopg2
from psycopg2 import extras, sql
import sys
import json
import re
import os
import logging
from datetime import datetime
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

    Additionally, table name must not start or end with the . character. 
    Column name must not contain . -
    """
    special_characters = '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ '
    ret = msg.lstrip(special_characters).rstrip(special_characters)
    ret = ret.upper().replace(" ", "_").replace("-","_")
    ret = re.sub(r'[^\w\s]', '', ret)
    ret = re.sub(r'_+', '_', ret)

    return ret


def parse_json(json_obj: dict) -> list:
    """
    Main parser used at this time, takes a json.loads object.
    """
    parsed_data = []

    try:
        broker_id = json_obj['broker_correlation_id']
        l_uid = json_obj['l_uid']
        p_uid = json_obj['p_uid']
        timestamp = parser.parse(json_obj['timestamp'])
        timeseries = json_obj['timeseries']

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


def parse_json_file(filename: str) -> list:
    parsed_data = []
    with open(filename, 'r') as f:
        json_str = ""
        for line in f:
            json_str += line.strip()
            try:
                json_data = json.loads(json_str)
                broker_id = json_data['broker_correlation_id']
                l_uid = json_data['l_uid']
                p_uid = json_data['p_uid']
                timestamp = parser.parse(json_data['timestamp'])
                timeseries = json_data['timeseries']

                for tsd in timeseries:
                    name = tsd['name']
                    value = tsd['value']
                    parsed_data.append((broker_id, p_uid, l_uid, timestamp, name, value))

                json_str = ""
            except json.decoder.JSONDecodeError as e:
                logging.error(f"An error occurred: {str(e)}")
                pass

    return parsed_data


# Method for full insert to DB from file, not in use currently.
def insert_file_to_db(filename: str, connection: str = CONNECTION, table_name: str = tsdb_table) -> int:
    # Parse the JSON file
    parsed_data = parse_json_file(filename)
    conn = psycopg2.connect(connection)
    cursor = conn.cursor()
    # Insert parsed data into the database
    try:
        for data in parsed_data:
            broker_id, l_uid, p_uid, timestamp, name, value = data
            insert_query = f"INSERT INTO {table_name} (broker_id, l_uid, p_uid, timestamp, name, value) VALUES (%s, %s, %s, %s, %s, %s)"
            cursor.execute(insert_query, (broker_id, l_uid, p_uid, timestamp, name, value))
    except (Exception, psycopg2.Error) as error:
        print(error)
        return 0
    conn.commit()
    cursor.close()
    return 1


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


# For getting data from the database.
def send_query(query: str, interval_hrs: int = 24, connection: str = CONNECTION, table: str = tsdb_table):
    conn = psycopg2.connect(connection)
    cursor = conn.cursor()
    try:
        cursor.execute(query)
        conn.commit()
        result = cursor.fetchall()
    except psycopg2.errors as e:
        sys.stderr.write(f'error: {e}\n')
    cursor.close()
    return result


def query_all_data(connection: str = CONNECTION, table: str = tsdb_table):
    conn = psycopg2.connect(connection)
    cursor = conn.cursor()
    query = f"SELECT * FROM {table};"
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    json_data = []
    for row in rows:
        # Convert datetime object to string before loading as JSON
        timestamp_str = row[3].isoformat()
        json_obj = {
            "broker_id": row[0],
            "l_uid": row[1],
            "p_uid": row[2],
            "timestamp": timestamp_str,
            "name": row[4],
            "value": row[5]
        }
        json_data.append(json_obj)
    return json_data


def remove_data_with_value(value: str = "",connection: str = CONNECTION, table: str = tsdb_table):
    if (value == ""):
        query = f"DELETE FROM {table}"
    else:
        query = f"""DELETE FROM {table}
                WHERE value = '{value}';"""
    conn = psycopg2.connect(connection)
    cursor = conn.cursor()
    cursor.execute(query)
    conn.commit()
    cursor.close()
