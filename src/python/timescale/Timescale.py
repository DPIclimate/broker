import psycopg2
from psycopg2 import extras, sql
import sys
import json
import random
import logging
from datetime import datetime
from dateutil import parser

username = "postgres"
password = "admin"
host = "tsdb"   # Container hostname, for Docker communication.
port = 5432 
dbname = "postgres"
table_name = "timeseries"
CONNECTION = f"postgres://{username}:{password}@{host}:{port}/{dbname}"

def create_test_table(connection: str = CONNECTION, table: str = table_name):
    query_create_table = f"""CREATE TABLE {table} (
                                        broker_id VARCHAR,
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
        cursor.execute(f"SELECT create_hypertable('{table}', 'timestamp');")
        # commit changes to the database to make changes persistent
        conn.commit()
    except psycopg2.errors.DuplicateTable as e:
        sys.stderr.write(f'error: {e}\n')
    cursor.close()

    # Produce the test temperature data that is inserted.
def generate_test_message():
    json_example = []
    for i in range(2):
        rand_cor_id = random.randint(100000, 999999)
        rand_value = random.randint(0, 45)
        rand_id = random.randint(140, 200)
        json_item = f'{{"broker_correlation_id": "{rand_cor_id}" "l_uid": "{rand_id}", "p_uid": "{rand_id + 1}", "name": "temperature", "value": "{rand_value}"}}'
        json_example.append(json_item)
        return json_example

# def insert_lines(json_entries: list = generate_test_message(), connection: str = CONNECTION,):
#     conn = psycopg2.connect(connection)
#     cursor = conn.cursor()
#     try:
#         for json_data in json_entries:
#         # Parse the JSON message and extract the relevant data fields
#             data = json.loads(json_data)
#             l_uid = data['l_uid']
#             p_uid = data['p_uid']
#             name = data['name']
#             value = data['value']

#             cursor.execute("INSERT INTO test_table (l_uid, p_uid, timestamp, name, value) VALUES (%s, %s, CURRENT_TIMESTAMP, %s, %s);",
#                            (l_uid, p_uid, name, value))
#     except (Exception, psycopg2.Error) as error:
#         print(error)
#     conn.commit()

def insert_lines(parsed_data: list, connection: str = CONNECTION, table: str = table_name) -> int:
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

# For efficiency
def insert_lines_bulk(parsed_data: list, connection: str = CONNECTION, table: str = table_name) -> int:
    try:
        # Connect to the database and create a cursor
        conn = psycopg2.connect(connection)
        cursor = conn.cursor()

        # Prepare a list of tuples containing the data to be inserted
        data_to_insert = []
        for entry in parsed_data:
            broker_id = entry[0]
            l_uid = entry[1]
            p_uid = entry[2]
            timestamp = entry[3]
            name = entry[4]
            value = entry[5]
            data_to_insert.append((broker_id, l_uid, p_uid, timestamp, name, value))

        # Define the chunk size for bulk insert
        chunk_size = 500

        # Divide data_to_insert into chunks of chunk_size
        for i in range(0, len(data_to_insert), chunk_size):
            chunk = data_to_insert[i:i + chunk_size]

            # Define the SQL statement for the bulk insert
            sql_statement = f"INSERT INTO {table} (broker_id, l_uid, p_uid, timestamp, name, value) VALUES %s;"

            # Log the SQL statement for debugging
            print("SQL Statement:", sql_statement)
            print("Data to Insert:", chunk)

            # Execute the bulk insert for the current chunk
            psycopg2.extras.execute_values(cursor, sql_statement, chunk)

        conn.commit()  # Commit the transaction if everything is successful

        return 1

    except (Exception, psycopg2.Error) as error:
        print("Error during bulk insert:")
        print(error)
        conn.rollback()  # Rollback the transaction to avoid partial inserts

    finally:
        cursor.close()
        conn.close()

    return 0

    
def query_all_data(connection: str = CONNECTION, table: str = table_name):
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

def query_avg_value(interval_hrs: int = 24, connection: str = CONNECTION, table: str = table_name ):
    query_avg = f"""SELECT AVG(value) FROM {table}
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

def query_num_entries(connection: str = CONNECTION, table: str = table_name ):
    query_avg = f"SELECT COUNT(*) FROM {table};"
    conn = psycopg2.connect(connection)
    cursor = conn.cursor()
    try:
        cursor.execute(query_avg)
        conn.commit()
        result = cursor.fetchone()[0]
    except psycopg2.errors as e:
        sys.stderr.write(f'error: {e}\n')
    cursor.close()
    return result

def remove_data_with_value(value: str = "",connection: str = CONNECTION, table: str = table_name):
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

# Main parser used at this time, takes a json.loads object.
def parse_json(json_obj: dict) -> list:
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
        return []
    
    return parsed_data

def parse_json_string(json_string: str) -> list:
    try:
        json_obj = json.loads(json_string)
        return parse_json(json_obj)
    except json.JSONDecodeError as e:
        logging.error(f"An error occurred: {str(e)}")
        return []


# def parse_json_string(json_string: str) -> list:
#     parsed_data = []
#     json_str = ""

#     for line in json_string.split('\n'):
#         json_str += line.strip()
#         try:
#             json_obj = json.loads(json_str)
#             broker_id = json_obj['broker_correlation_id']
#             l_uid = json_obj['l_uid']
#             p_uid = json_obj['p_uid']
#             timestamp = parser.parse(json_obj['timestamp'])
#             timeseries = json_obj['timeseries']

#             for tsd in timeseries:
#                 name = tsd['name']
#                 value = tsd['value']
#                 parsed_data.append((broker_id, l_uid, p_uid, timestamp, name, value))

#             json_str = ""
#         except json.decoder.JSONDecodeError as e:
#             logging.error(f"An error occurred: {str(e)}")
#             pass

#     return parsed_data


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
            except json.decoder.JSONDecodeError:
                logging.error(f"An error occurred: {str(e)}")
                pass

    return parsed_data


def insert_data_to_db(filename: str, connection: str = CONNECTION, table_name: str = table_name) -> int:
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
    

test_message = """{
  "broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6",
  "p_uid": 301,
  "l_uid": 276,
  "timestamp": "2023-01-30T06:21:56Z",
  "timeseries": [
    {
      "name": "battery (v)",
      "value": 4.16008997
    },
    {
      "name": "pulse_count",
      "value": 1
    },
    {
      "name": "1_Temperature",
      "value": 21.60000038
    }
  ]
}
"""

if __name__ == "__main__":
    create_test_table()
    #lol = parse_json_string(test_message)
    #print(lol)
    #insert_lines(lol)
    #insert_data_to_db("JSON_message")
    #insert_data_to_db("sample_messages")
    print(query_all_data())