import psycopg2
import sys
import json
import random
from datetime import datetime
from dateutil import parser

username = "postgres"
password = "admin"
host = "localhost"
port = 5433     # Not 5432 since postgres already exists in stack
dbname = "postgres"
CONNECTION = f"postgres://{username}:{password}@{host}:{port}/{dbname}"

def create_test_table(connection: str = CONNECTION):
    query_create_table = """CREATE TABLE test_table (
                                        l_uid VARCHAR,
                                        p_uid VARCHAR,
                                        timestamp TIMESTAMPTZ NOT NULL,
                                        name VARCHAR,
                                        value VARCHAR
                                    );
                                    """
    conn = psycopg2.connect(connection)
    cursor = conn.cursor()
    try:
        cursor.execute(query_create_table)
        # Creates a hypertable for time-based partitioning
        cursor.execute("SELECT create_hypertable('test_table', 'timestamp');")
        # commit changes to the database to make changes persistent
        conn.commit()
    except psycopg2.errors.DuplicateTable as e:
        sys.stderr.write(f'error: {e}\n')
    cursor.close()

    # Produce the test temperature data that is inserted.
def generate_test_message():
    json_example = []
    for i in range(2):
        rand_value = random.randint(0, 45)
        rand_id = random.randint(140, 200)
        json_item = f'{{"l_uid": "{rand_id}", "p_uid": "{rand_id + 1}", "name": "temperature", "value": "{rand_value}"}}'
        json_example.append(json_item)
        return json_example

def insert_lines(json_entries: list = generate_test_message(), connection: str = CONNECTION,):
    conn = psycopg2.connect(connection)
    cursor = conn.cursor()
    try:
        for json_data in json_entries:
        # Parse the JSON message and extract the relevant data fields
            data = json.loads(json_data)
            l_uid = data['l_uid']
            p_uid = data['p_uid']
            name = data['name']
            value = data['value']

            cursor.execute("INSERT INTO test_table (l_uid, p_uid, timestamp, name, value) VALUES (%s, %s, CURRENT_TIMESTAMP, %s, %s);",
                           (l_uid, p_uid, name, value))
    except (Exception, psycopg2.Error) as error:
        print(error)
    conn.commit()
    

def query_all_data(connection: str = CONNECTION):
    conn = psycopg2.connect(connection)
    cursor = conn.cursor()
    query = "SELECT * FROM test_table;"
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()

    json_data = []
    for row in rows:
        # Convert datetime object to string before loading as JSON
        timestamp_str = row[2].isoformat()
        json_obj = {
            "l_uid": row[0],
            "p_uid": row[1],
            "timestamp": timestamp_str,
            "name": row[3],
            "value": row[4]
        }
        json_data.append(json_obj)
    return json_data

def query_avg_value(interval_hrs: int = 24, connection: str = CONNECTION, table_name: str = "test_table"):
    query_avg = f"""SELECT AVG(value) FROM {table_name}
                            WHERE timestamp > NOW() - INTERVAL '{interval_hrs} hours';
                            """
    conn = psycopg2.connect(connection)
    cursor = conn.cursor()
    try:
        cursor.execute(query_avg)
        conn.commit()
        result = cursor.fetchone()
    except psycopg2.errors as e:
        sys.stderr.write(f'error: {e}\n')
    cursor.close()
    return result

#     # Old file method, format specific.
# def insert_data_json_file(filename: str, connection: str = CONNECTION, table_name: str = "test_table"):
#     # Open the JSON file and load its contents
#     with open(filename, 'r') as f:
#         data = json.load(f)

#     # Extract the ID, timestamp, and timeseries data from the JSON data
#     l_uid = data['l_uid']
#     p_uid = data['p_uid']
#     timestamp = datetime.strptime(data['timestamp'], '%Y-%m-%dT%H:%M:%SZ')
#     timeseries = data['timeseries']

#     conn = psycopg2.connect(connection)
#     cur = conn.cursor()

#     # Extract the timeseries data and insert it into the database
#     for tsd in timeseries:
#         name = tsd['name']
#         value = tsd['value']
#         insert_query = f"INSERT INTO {table_name} (l_uid, p_uid, timestamp, name, value) VALUES (%s, %s, %s, %s, %s)"
#         cur.execute(insert_query, (l_uid, p_uid, timestamp, name, value))

#     conn.commit()
#     conn.close()


def parse_json_string(json_string: str) -> list:
    parsed_data = []
    json_str = ""

    for line in json_string.split('\n'):
        json_str += line.strip()
        try:
            json_data = json.loads(json_str)
            l_uid = json_data['l_uid']
            p_uid = json_data['p_uid']
            timestamp = parser.parse(json_data['timestamp'])
            timeseries = json_data['timeseries']

            for tsd in timeseries:
                name = tsd['name']
                value = tsd['value']
                parsed_data.append((l_uid, p_uid, timestamp, name, value))

            json_str = ""
        except json.decoder.JSONDecodeError:
            pass

    return parsed_data


def parse_json_file(filename: str) -> list:
    parsed_data = []

    with open(filename, 'r') as f:
        json_str = ""
        for line in f:
            json_str += line.strip()
            try:
                json_data = json.loads(json_str)
                l_uid = json_data['l_uid']
                p_uid = json_data['p_uid']
                timestamp = parser.parse(json_data['timestamp'])
                timeseries = json_data['timeseries']

                for tsd in timeseries:
                    name = tsd['name']
                    value = tsd['value']
                    parsed_data.append((l_uid, p_uid, timestamp, name, value))

                json_str = ""
            except json.decoder.JSONDecodeError:
                pass

    return parsed_data


def insert_data_to_db(filename: str, connection: str = CONNECTION, table_name: str = "test_table"):
    # Parse the JSON file
    parsed_data = parse_json_file(filename)

    conn = psycopg2.connect(connection)
    cur = conn.cursor()

    # Insert parsed data into the database
    for data in parsed_data:
        l_uid, p_uid, timestamp, name, value = data
        insert_query = f"INSERT INTO {table_name} (l_uid, p_uid, timestamp, name, value) VALUES (%s, %s, %s, %s, %s)"
        cur.execute(insert_query, (l_uid, p_uid, timestamp, name, value))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_test_table()
    insert_lines()
    #insert_data_to_db("JSON_message")
    # insert_data_to_db("sample_messages")
    print(query_all_data())