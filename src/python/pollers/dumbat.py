"""
The Dumbat is a tool to test the Integration of the Intersect data wrangling code into
IoTa. It can read Wombat messages from a directory tree or an IoTa physical_timeseries table
and feed them to a Wombat receiver via MQTT.

The rate of message delivery can be specified to stress test the code.

"""

import datetime as dt
import logging
import time
import psycopg2 as pg
from pathlib import Path
import os
import paho.mqtt.client as mqtt


mqtt_host = os.environ['RABBITMQ_HOST']
mqtt_port = os.environ['RABBITMQ_PORT']
mqtt_user = os.environ['RABBITMQ_DEFAULT_USER']
mqtt_password = os.environ['RABBITMQ_DEFAULT_PASS']

sleep_time = 1 / 50

mqttc = None


def filewalker():
    connect_mqtt()

    msg_count = 0
    msg_root_dir = Path('scmn_msgs')
    for dirpath, dirnames, filenames in msg_root_dir.walk():
        dirnames.sort()
        for filename in filenames:
            if not filename.endswith('.json'):
                continue

            #logging.info(dirpath / filename)
            with open(dirpath / filename, 'rt') as fp:
                msg_text = fp.read()
                msg_info = mqttc.publish('wombat', msg_text, qos=1)
                msg_info.wait_for_publish()
                #time.sleep(sleep_time)
                msg_count += 1
                if msg_count % 10000 == 0:
                    logging.info(f'Posted {msg_count} messages.')


def scmn_source_reader():
    connect_mqtt()

    # 2024-07-13 13:07:30+10
    ts = dt.datetime(year=2024, month=7, day=13, hour=13, minute=7, second=30, tzinfo=dt.timezone.utc)

    msg_count = 0
    scmn_conn = None
    try:
        scmn_conn = pg.connect('dbname=broker host=localhost port=6432 user=postgres password=CHANGEME')
        scmn_conn.autocommit = True
        scmn_conn.set_session(readonly=True)
        with scmn_conn.cursor() as curs:
            while True:
                curs.execute("""select ts, json_msg::text from raw_messages where ts > %s order by ts limit 1000""", (ts,))
                if curs.rowcount < 1:
                    break

                for row in curs.fetchall():
                    ts = row[0]
                    msg_text = row[1]
                    msg_info = mqttc.publish('wombat', msg_text, qos=1)
                    msg_info.wait_for_publish()
                    time.sleep(sleep_time)
                    msg_count += 1
                    if msg_count % 10000 == 0:
                        logging.info(f'Posted {msg_count} messages.')

    except:
        logging.exception('Error publishing message')
    finally:
        if scmn_conn is not None:
            scmn_conn.close()


def connect_to_central():
    conn = pg.connect('dbname=x host=x port=5432 user=x password=x')
    conn.autocommit = True
    return conn


def connect_to_iota():
    conn = pg.connect('dbname=x host=x port=5432 user=x password=x')
    conn.autocommit = True
    return conn


def connect_mqtt() -> None:
    global mqttc

    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqttc.username_pw_set(mqtt_user, mqtt_password)

    mqttc.loop_start()

    mqttc.connect('localhost')
    while not mqttc.is_connected():
        logging.warning('Not connected.')
        time.sleep(2)

    logging.info('MQTT connected.')


def check_data() -> None:
    c_conn = None
    i_conn = None

    try:
        c_conn = connect_to_central()
        c_conn.set_session(readonly=True)

        i_conn = connect_to_iota()
        i_conn.set_session(readonly=True)

        limit = 16384
        offset = 0
        count = 0

        with i_conn.cursor() as i_curs:
            with c_conn.cursor() as c_curs:
                while True:
                    i_curs.execute('select ts,location_id,sensor_serial_id,position,variable,value from main.sensors order by location_id, ts, position, variable limit %s offset %s', (limit, offset))
                    if i_curs.rowcount < 1:
                        break

                    offset = offset + i_curs.rowcount
                    for i_row in i_curs.fetchall():
                        where_vals = (i_row[1], i_row[0], i_row[3], i_row[4])

                        count = count + 1
                        if count % 10000 == 0:
                            logging.info(f'Read {count} rows')

                        c_curs.execute('select ts,location_id,sensor_serial_id,position,variable,value from main.sensors where location_id = %s and ts = %s and position = %s and variable = %s', where_vals)
                        if c_curs.rowcount != 1:
                            logging.error(f'Fetched {c_curs.rowcount} rows')
                            continue

                        c_row = c_curs.fetchone()
                        diff_str = ''

                        if i_row != c_row:
                            v_diff = round(abs(i_row[5] - c_row[5]), 3)
                            if v_diff != 0:
                                diff_str = f'diff {v_diff}'

                        if len(diff_str):
                            logging.warning(f'{c_row[1]} {c_row[2]} {c_row[3]} {c_row[4]} {c_row[5]} {i_row[5]} {diff_str} {c_row[0].isoformat()}')
                        else:
                            logging.info(f'{c_row[1]} {c_row[2]} {c_row[3]} {c_row[4]} {c_row[5]} {i_row[5]}')

    finally:
        if c_conn is not None:
            c_conn.close()

        if i_conn is not None:
            i_conn.close()


def look_for_wrong_row_count() -> None:
    c_conn = None
    i_conn = None

    try:
        c_conn = connect_to_central()
        c_conn.set_session(readonly=True)

        i_conn = connect_to_iota()
        i_conn.set_session(readonly=True)

        limit = 16384
        offset = 0
        count = 0

        with i_conn.cursor() as i_curs:
            with c_conn.cursor() as c_curs:
                while True:
                    i_curs.execute('select ts,location_id,broker_correlation_id,sensor_serial_id,position,variable,value from main.sensors order by location_id, ts, position, variable limit %s offset %s', (limit, offset))
                    if i_curs.rowcount < 1:
                        break

                    offset = offset + i_curs.rowcount
                    for i_row in i_curs.fetchall():
                        where_vals = (i_row[1], i_row[0], i_row[4], i_row[5])

                        count = count + 1
                        if count % 10000 == 0:
                            logging.info(f'Read {count} rows')

                        c_curs.execute('select ts,location_id,broker_correlation_id,sensor_serial_id,position,variable,value from main.sensors where location_id = %s and ts = %s and position = %s and variable = %s', where_vals)
                        if c_curs.rowcount == 1:
                            continue

                        logging.info('Row from IoTa')
                        logging.info(i_row)
                        if c_curs.rowcount < 1:
                            logging.info('Not found in central')
                        else:
                            logging.info('Rows from central')
                            for c_row in c_curs:
                                logging.info(c_row)

                        logging.info('------------------------------------------------------------------------------')

    finally:
        if c_conn is not None:
            c_conn.close()

        if i_conn is not None:
            i_conn.close()


if __name__ == '__main__':
    try:
        #check_data()
        look_for_wrong_row_count()
        #filewalker()
        #scmn_source_reader()
    finally:
        if mqttc is not None:
            mqttc.disconnect()
            mqttc.loop_stop()
