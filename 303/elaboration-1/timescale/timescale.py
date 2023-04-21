import psycopg2
import sys
import json
import random
from datetime import datetime

username = "postgres"
password = "admin"
host = "localhost"
port = 5432
dbname = "postgres"
CONNECTION = f"postgres://{username}:{password}@{host}:{port}/{dbname}"

# Produce the test temperature data that is inserted.
json_example = []
for i in range(2):
    rand_value = random.randint(0, 45)
    rand_id = random.randint(140, 200)
    json_item = f'{{"ID": "{rand_id}", "type": "temp", "value": "{rand_value}"}}'
    json_example.append(json_item)

def create_test_table(connection: str = CONNECTION):
    query_create_table = """CREATE TABLE test_table (
                                        ID VARCHAR,
                                        time TIMESTAMPTZ NOT NULL,
                                        type VARCHAR,
                                        value DOUBLE PRECISION
                                    );
                                    """
    conn = psycopg2.connect(connection)
    cursor = conn.cursor()
    try:
        cursor.execute(query_create_table)
        # Creates a hypertable for time-based partitioning
        cursor.execute("SELECT create_hypertable('test_table', 'time');")
        # commit changes to the database to make changes persistent
        conn.commit()
    except psycopg2.errors.DuplicateTable as e:
        sys.stderr.write(f'error: {e}\n')
    cursor.close()

## Working with data in list format, possibly useful if another method parses JSON format.
# def insert_lines(connection: str = CONNECTION, test_entries: list = [('defaulttype', '12345')]):
#     conn = psycopg2.connect(connection)
#     cursor = conn.cursor()
#     for entry in test_entries:
#         try: 
#             cursor.execute("INSERT INTO test_table (time, type, value) VALUES (CURRENT_TIMESTAMP, %s, %s);",
#                         (entry[0], entry[1]))
#         except (Exception, psycopg2.Error) as error:
#             print(error.pgerror)
#     conn.commit()

def insert_lines(json_entries: list = json_example, connection: str = CONNECTION,):
    conn = psycopg2.connect(connection)
    cursor = conn.cursor()
    try:
        for json_data in json_entries:
        # Parse the JSON message and extract the relevant data fields
            data = json.loads(json_data)
            id = data['ID']
            test_type = data['type']
            test_value = data['value']

            cursor.execute("INSERT INTO test_table (id, time, type, value) VALUES (%s, CURRENT_TIMESTAMP, %s, %s);",
                           (id, test_type, test_value))
    except (Exception, psycopg2.Error) as error:
        print(error.pgerror)
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
        timestamp_str = row[1].isoformat()
        json_obj = {
            "ID": row[0],
            "time": timestamp_str,
            "type": row[2],
            "value": row[3]
        }
        json_data.append(json_obj)
    return json_data

def query_avg_value(interval_hrs: int = 24, connection: str = CONNECTION, table_name: str = "test_table"):
    query_avg = f"""SELECT AVG(value) FROM {table_name}
                            WHERE time > NOW() - INTERVAL '{interval_hrs} hours';
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

def insert_data_json_file(filename: str, connection: str = CONNECTION, table_name: str = "test_table"):
    # Open the JSON file and load its contents
    with open(filename, 'r') as f:
        data = json.load(f)

    # Extract the ID, timestamp, and timeseries data from the JSON data
    id = data['ID']
    timestamp = datetime.strptime(data['timestamp'], '%Y-%m-%dT%H:%M:%SZ')
    timeseries = data['timeseries']

    conn = psycopg2.connect(connection)
    cur = conn.cursor()

    # Extract the timeseries data and insert it into the database
    for tsd in timeseries:
        type = tsd['type']
        value = tsd['value']
        insert_query = f"INSERT INTO {table_name} (id, time, type, value) VALUES (%s, %s, %s, %s)"
        cur.execute(insert_query, (id, timestamp, type, value))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_test_table()
    #insert_lines()
    insert_data_json_file("jsondata.txt")
    print(query_all_data())
    print(query_avg_value())