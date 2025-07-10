import datetime as dt
import json
import logging
import os
import time
import uuid
from typing import Dict, Optional

import dateutil.tz as dtz
import dateutil.parser as dup
import pandas as pd
import pika
import pika.adapters.blocking_connection as pab
import pika.channel
import pika.spec
import pprint
import requests
from pika.exchange_type import ExchangeType

import BrokerConstants
import api.client.DAO as dao
import util.LoggingUtil as lu
from pdmodels.Models import PhysicalDevice

_user = os.environ['RABBITMQ_DEFAULT_USER']
_passwd = os.environ['RABBITMQ_DEFAULT_PASS']
_host = os.environ['RABBITMQ_HOST']
_port = os.environ['RABBITMQ_PORT']

_amqp_url_str = f'amqp://{_user}:{_passwd}@{_host}:{_port}/%2F'

_connection: pab.BlockingConnection = None
_channel: pab.BlockingChannel = None

_api_token = os.getenv('AXISTECH_TOKEN')

_recent_msg_times: Dict[str, dt.datetime] = {}
"""
Holds the most recent message timestamp for each AxisTech device. Keyed by device code.
"""


_sydney_tz = dtz.gettz('Australia/Sydney')


def local_time_str(ts: dt.datetime) -> str:
    """
    Return an AE[S|D]T string representation of ts, eg '16/01/2024 23:11'
    """
    return ts.astimezone(_sydney_tz).strftime('%d/%m/%Y %H:%M')


def z_ts(ts: dt.datetime) -> str:
    """
    AxisTech will only accept start and end timestamps with a time component in the form YYYY-MM-DDThh:mm:ssZ,
    so this function takes a datetime object and returns it formatted as described, by converting to UTC if
    necessary and then replacing the +00:00 tz suffix with Z.
    """
    return ts.astimezone(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def make_msg(row: pd.Series) -> Dict:
    """
    Transform a row from the DataFrame with the AxisTech data into a row with an IoTa format message.
    """
    serial_no, ts = row.name
    values = dict(zip(row.index.values, row.values))
    correlation_id = str(uuid.uuid4())
    str_timestamp = ts.isoformat(timespec='seconds')
    if str_timestamp.endswith('+00:00'):
        str_timestamp = str_timestamp.replace('+00:00', 'Z')

    source_ids = {'serial_no': serial_no, 'sdi-12': [f'813AXSTECH AWS   000{serial_no}']}
    msg = {BrokerConstants.TIMESTAMP_KEY: str_timestamp, 'source_ids': source_ids,
           BrokerConstants.TIMESERIES_KEY: [], BrokerConstants.CORRELATION_ID_KEY: correlation_id}

    for name, value in values.items():
        msg['timeseries'].append({'name': name, 'value': None if pd.isna(value) else value})

    return msg


def process_msg(msg: Dict) -> None:
    """
    Send a message onto the rest of IoTa.
    """
    global _connection, _channel

    ts = dup.parse(msg[BrokerConstants.TIMESTAMP_KEY])
    serial_no = msg["source_ids"]["serial_no"]
    source_ids = msg['source_ids']

    dao.add_raw_json_message(BrokerConstants.AXISTECH, ts, msg[BrokerConstants.CORRELATION_ID_KEY], msg)

    pds = dao.get_pyhsical_devices_using_source_ids(BrokerConstants.AXISTECH, source_ids)
    if len(pds) < 1:
        lu.cid_logger.info(f'Physical device not found for device {serial_no}, creating a new one.', extra=msg)

        props = {BrokerConstants.CREATION_CORRELATION_ID_KEY: msg[BrokerConstants.CORRELATION_ID_KEY],
            BrokerConstants.LAST_MSG: json.dumps(msg)}

        pdev = PhysicalDevice(source_name=BrokerConstants.AXISTECH, name=serial_no, location=None,
                            source_ids=source_ids, properties=props)
        pdev = dao.create_physical_device(pdev)
    else:
        lu.cid_logger.info(f'Accepted message from {serial_no}, updating last seen time to {ts}.', extra=msg)
        pdev = pds[0]
        pdev.properties[BrokerConstants.LAST_MSG] = json.dumps(msg)

    msg[BrokerConstants.PHYSICAL_DEVICE_UID_KEY] = pdev.uid
    lu.cid_logger.info(f'Posting msg: {msg}', extra=msg)
    _channel.basic_publish(BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME, 'physical_timeseries', json.dumps(msg).encode('UTF-8'))
    _connection.process_data_events(0)

    # Update last seen here so if the publish fails and the process restarts, the message will be reprocessed because
    # it is less than the device's last_seen time.
    pdev.last_seen = ts
    dao.update_physical_device(pdev)


def get_messages(start: dt.datetime, end: dt.datetime) -> Optional[pd.DataFrame]:
    global _recent_msg_times

    drop_cols = ['wind_dir_var_avg', 'uv_index_avg']
    """
    Columns in the AxisTech message that have no equivalent in the SCMN ATM-41 messages, so these get dropped.
    """

    atm41_col_names = ['8_Precipitation', '8_AirTemperature', '8_WindSpeed', '8_WindSpeed_max', '8_RH', '8_AirPressure',
        '8_DeltaT', '8_DewPoint', '8_Solar', '8_WindDirection', '8_WindSpeed_min']
    """
    The variable names to use to make the AxisTech message look like an SCMN ATM-41 message.
    """

    try:
        url = f'https://data.exchange.axisstream.co/?token={_api_token}&startDate={z_ts(start)}&endDate={z_ts(end)}'
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()

        if 'bb5d4f86-6eaa-494d-abcc-8f2e9b66b214' not in data['data']:
            logging.warning('Did not find expected UUID in data object.')
            logging.warning(pprint.pformat(data))
            return None

        frames = []
        counter = 0
        for info in data['data']['bb5d4f86-6eaa-494d-abcc-8f2e9b66b214']['weather']:
            code = info['code']
            ts = dup.parse(info['time'])
            if code not in _recent_msg_times or ts > _recent_msg_times[code]:
                _recent_msg_times[code] = ts
                frame = pd.DataFrame(info, index=[counter])
                frames.append(frame)
                counter += 1

        if counter < 1:
            return None

        df = pd.concat(frames, axis=0)
        df['rainfall'] = df['rainfall'].astype(float)
        df['humidity_avg'] = df['humidity_avg'].astype(float)
        df['temperature_avg'] = df['temperature_avg'].astype(float)
        df['wind_speed_avg'] = df['wind_speed_avg'].astype(float)
        df['wind_speed_max'] = df['wind_speed_max'].astype(float)
        df['atmos_pressure_avg'] = df['atmos_pressure_avg'].astype(float)
        df['deltat_avg'] = df['deltat_avg'].astype(float)
        df['dewpoint_avg'] = df['dewpoint_avg'].astype(float)
        df['solar_rad_avg'] = df['solar_rad_avg'].astype(float)
        df['uv_index_avg'] = df['uv_index_avg'].astype(float)
        df['wind_dir_deg_avg'] = df['wind_dir_deg_avg'].astype(float)
        df['wind_speed_min'] = df['wind_speed_min'].astype(float)
        df['time'] = pd.to_datetime(df['time'])

        # Use a MultiIndex to make grouping by code easy later on.
        df.set_index(['code', 'time'], inplace=True)
        df.index = df.index.sort_values()

        # Apply column header changes
        df.drop(drop_cols, inplace=True, axis=1)
        df.columns = atm41_col_names

        return df

    except BaseException as e:
        logging.exception(e)

    return None


def poll() -> None:
    # The reason for such a large window time is that the AxisTech API is slow to provide new messages
    # and seems to lag hours behind. If we poll every hour and don't ask for too big a window, it should not
    # place too high a load on their servers.
    #
    # If we only ever polled for say the last hour, we'd rarely if ever get any messages.
    end_ts = dt.datetime.now(dt.timezone.utc)
    start_ts = end_ts - dt.timedelta(days=5)

    # Find the earliest 'most recent' message time. If one can be found there is no point asking for
    # messages from before then because they've already been seen. One hole in this logic would be
    # if a new device is added to AxisTech, it's first messages may be missed.
    some_ts = None
    for code, ts in _recent_msg_times.items():
        if some_ts is None or ts < some_ts:
            some_ts = ts

    # If a message has been seen more recently than the default start_ts value, only ask for messages since the
    # timestamp of the received messages. This risks missing messages from a code that are older than the default
    # start of the window if the code has not sent a message in longer than that, but the alternative is to risk
    # the window growing indefinitely if a device goes offline.
    if some_ts is not None and some_ts > start_ts:
        logging.info(f'Adjusting start_ts, was {local_time_str(start_ts)}, will be {local_time_str(some_ts)}')
        start_ts = some_ts

    logging.info(f'Polling for message between {z_ts(start_ts)} and {z_ts(end_ts)}, [{local_time_str(start_ts)} to {local_time_str(end_ts)}]')
    msgs_df = get_messages(start_ts, end_ts)
    if msgs_df is None:
        logging.info('No new messages')
        return

    # Group the dataframe rows by device code.
    code_groups = msgs_df.groupby(level=0)

    logging.info('New messages')
    # For each device code subset of the dataframe, apply the function to create the messages. The function is given
    # a pd.Series that contains all the info for one row.
    for code, code_df in code_groups:
        code_df.apply(make_msg, axis=1).apply(process_msg)

    logging.info(f'Latest message times: {_recent_msg_times}')


def main() -> None:
    global _connection, _channel

    logging.info('===============================================================')
    logging.info('               STARTING AXISTECH POLLER')
    logging.info('===============================================================')

    dao.add_physical_source(BrokerConstants.AXISTECH)

    # Initialise the most recent message timestamp cache. This is used to control the time window
    # used in the AxisTech API calls.
    for pdev in dao.get_physical_devices_from_source(BrokerConstants.AXISTECH):
        _recent_msg_times[pdev.source_ids['serial_no']] = pdev.last_seen

    try:
        logging.info('Opening connection')
        conn_attempts = 0
        backoff = 10
        while _connection is None:
            try:
                _connection = pika.BlockingConnection(pika.URLParameters(_amqp_url_str))
            except:
                conn_attempts += 1
                logging.warning(f'Connection to RabbitMQ attempt {conn_attempts} failed.')

                if conn_attempts % 5 == 0 and backoff < 60:
                    backoff += 10

                time.sleep(backoff)

        logging.info('Opening channel')
        _channel = _connection.channel()
        _channel.basic_qos(prefetch_count=1)
        logging.info('Declaring exchange')
        _channel.exchange_declare(exchange=BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME,
            exchange_type=ExchangeType.fanout, durable=True)

        sleep_time = 1800 # seconds
        while True:
            poll()
            _connection.process_data_events(sleep_time)

    except KeyboardInterrupt:
        logging.info('Stopping')
        dao.stop()

        if _connection is not None:
            _connection.close()


if __name__ == '__main__':
    main()

