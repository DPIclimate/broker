import argparse
import datetime as dt
import json
import logging
import math
import os
import time
import uuid
from typing import Dict, Optional, List

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

logger = logging.getLogger(__name__)

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
        lu.cid_logger.info(f'Accepted message from {serial_no} at {ts}.', extra=msg)
        pdev = pds[0]
        if pdev.last_seen is None or ts >= pdev.last_seen:
            pdev.properties[BrokerConstants.LAST_MSG] = json.dumps(msg)

    msg[BrokerConstants.PHYSICAL_DEVICE_UID_KEY] = pdev.uid
    lu.cid_logger.info(f'Posting msg: {msg}', extra=msg)
    _channel.basic_publish(BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME, 'physical_timeseries', json.dumps(msg).encode('UTF-8'))
    _connection.process_data_events(0)

    # Save progress only after publishing succeeds, so failed messages remain eligible for retry.
    if pdev.last_seen is None or ts > pdev.last_seen:
        pdev.last_seen = ts
    dao.update_physical_device(pdev)
    _recent_msg_times[serial_no] = max(_recent_msg_times.get(serial_no, ts), pdev.last_seen)


def get_messages(start: dt.datetime, end: dt.datetime, *,
                 device_code: Optional[str] = None, backfill: bool = False) -> Optional[pd.DataFrame]:
    drop_cols = ['wind_dir_var_avg', 'uv_index_avg']
    """
    Columns in the AxisTech message that have no equivalent in the SCMN ATM-41 messages, so these get dropped.
    """

    atm41_col_names = ['8_Precipitation', '8_AirTemperature', '8_WindSpeed', '8_WindSpeed_max', '8_RH', '8_AirPressure',
        '8_DeltaT', '8_DewPoint', '8_Solar', '8_WindDirection', '8_WindSpeed_min']
    """
    The variable names to use to make the AxisTech message look like an SCMN ATM-41 message.
    """

    # Track selection locally without advancing the successfully processed timestamps.
    selected_times = {} if backfill else _recent_msg_times.copy()

    try:
        url = f'https://data.exchange.axisstream.co/?token={_api_token}&startDate={z_ts(start)}&endDate={z_ts(end)}'
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()

        if 'bb5d4f86-6eaa-494d-abcc-8f2e9b66b214' not in data['data']:
            logger.warning('Did not find expected UUID in data object.')
            logger.warning(pprint.pformat(data))
            if backfill:
                raise ValueError('AxisTech response is missing the expected data UUID')
            return None

        frames = []
        counter = 0
        weather = data['data']['bb5d4f86-6eaa-494d-abcc-8f2e9b66b214']['weather']
        # Process oldest first so advancing the timestamp does not skip newer unseen records.
        for info in sorted(weather, key=lambda info: dup.parse(info['time'])):
            code = info['code']
            if device_code is not None and code != device_code:
                continue
            ts = dup.parse(info['time'])
            if code not in selected_times or ts > selected_times[code]:
                selected_times[code] = ts
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
        df.sort_index(inplace=True)

        # Apply column header changes
        df.drop(drop_cols, inplace=True, axis=1)
        df.columns = atm41_col_names

        return df

    except Exception as e:
        logger.exception(e)
        if backfill:
            raise

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
        logger.info(f'Adjusting start_ts, was {local_time_str(start_ts)}, will be {local_time_str(some_ts)}')
        start_ts = some_ts

    logger.info(f'Polling for message between {z_ts(start_ts)} and {z_ts(end_ts)}, [{local_time_str(start_ts)} to {local_time_str(end_ts)}]')
    msgs_df = get_messages(start_ts, end_ts)
    if msgs_df is None:
        logger.info('No new messages')
        return

    # Group the dataframe rows by device code.
    code_groups = msgs_df.groupby(level=0)

    logger.info('New messages')
    # For each device code subset of the dataframe, apply the function to create the messages. The function is given
    # a pd.Series that contains all the info for one row.
    for code, code_df in code_groups:
        code_df.apply(make_msg, axis=1).apply(process_msg)

    logger.info(f'Latest message times: {_recent_msg_times}')

# 438 & 449 are the physical device ids for AxisTech WiFi AWS.
"""
[
  {
    "ts_utc": "2025-06-13T12:55:36+00:00"
  },
  {
    "ts_utc": "2025-06-13T12:50:36+00:00"
  },
  {
    "ts_utc": "2025-06-13T12:45:36+00:00"
  },
  {
    "ts_utc": "2025-06-13T12:40:36+00:00"
  }
]
"""

def get_msg_timestamps(p_uid: int, ts_after: dt.datetime, load_timestamps: bool = False, *,
                       save_timestamps: bool = True) -> List[dt.datetime]:
    output_file = f'{p_uid}.txt'
    if load_timestamps:
        ret_ts_list = []
        with open(output_file, encoding='utf-8') as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                try:
                    ts = dup.isoparse(line.strip())
                    if ts.tzinfo is None:
                        raise ValueError('Timestamp must include a timezone')
                except ValueError as exc:
                    raise ValueError(f'{output_file}:{line_number}: {exc}') from exc
                if ts > ts_after:
                    ret_ts_list.append(ts)
        ret_ts_list.sort()
        logger.info(f'Loaded {len(ret_ts_list)} timestamps from {output_file} after {ts_after.isoformat()}')
        if ret_ts_list:
            logger.info(f'First: {ret_ts_list[0].isoformat()}, last: {ret_ts_list[-1].isoformat()}, count: {len(ret_ts_list)}')
        return ret_ts_list

    logger.info(f'Fetching message timestamps for physical device {p_uid}, from {ts_after.isoformat()}')

    page_size = 65536
    page_end = dt.datetime.now(dt.timezone.utc)
    timestamps = set()
    while page_end > ts_after:
        page = dao.get_physical_timeseries_message(start=ts_after, end=page_end, count=page_size,
                                                  p_uid=p_uid, only_timestamp=True)
        if not page:
            break
        page_times = [dt.datetime.fromisoformat(item['ts_utc']) for item in page]
        timestamps.update(page_times)
        if len(page) < page_size:
            break
        # The DAO returns whole seconds. Any remaining records in the oldest
        # second have the same timestamp identity, which is already in the set.
        page_end = min(page_times) - dt.timedelta(microseconds=1)
    ret_ts_list = sorted(timestamps)
    if save_timestamps:
        with open(output_file, 'w', encoding='utf-8') as output:
            for ts in ret_ts_list:
                output.write(f'{ts.isoformat()}\n')

    if ret_ts_list:
        logger.info(f'First: {ret_ts_list[0].isoformat()}, last: {ret_ts_list[-1].isoformat()}, count: {len(ret_ts_list)}')
    if save_timestamps:
        logger.info(f'Wrote {len(ret_ts_list)} timestamps to {output_file}')
    return ret_ts_list


def backfill_messages(p_uid: int, start: dt.datetime, existing_timestamps: List[dt.datetime], *,
                      end: dt.datetime, dry_run: bool = False, forward_fill: bool = False,
                      message_delay: Optional[float] = None) -> int:
    """Process or preview missing messages in seven-day API windows; return their count."""
    if end <= start:
        raise ValueError('Backfill end date must be after the start date')
    if message_delay is None:
        message_delay = 1.0 if forward_fill else 0.0
    if not math.isfinite(message_delay) or message_delay < 0:
        raise ValueError('Message delay must be a finite, non-negative number')
    mode = 'Forward fill' if forward_fill else 'Backfill'

    pdev = dao.get_physical_device(p_uid)
    if pdev is None or pdev.source_name != BrokerConstants.AXISTECH:
        raise ValueError(f'Physical device {p_uid} is not an AxisTech device')
    code = pdev.source_ids.get('serial_no')
    if not code:
        raise ValueError(f'Physical device {p_uid} has no serial_no')

    # Message conversion and the stored timestamp query both use whole seconds.
    seen = {ts.astimezone(dt.timezone.utc).replace(microsecond=0) for ts in existing_timestamps}
    end = end.astimezone(dt.timezone.utc)
    if seen and not forward_fill:
        end = min(end, max(seen))
    elif not seen:
        logger.info('No existing timestamps; using the requested backfill end date')
    logger.info(f'{mode}: {start.isoformat()} to {end.isoformat()}, message delay: {message_delay}s')
    window_start = start.astimezone(dt.timezone.utc)
    processed = 0
    while window_start < end:
        window_end = min(window_start + dt.timedelta(days=7), end)
        logger.info(f'{mode} device {p_uid}: {z_ts(window_start)} to {z_ts(window_end)}')
        messages = get_messages(window_start, window_end, device_code=code, backfill=True)
        if messages is not None:
            for _, row in messages.iterrows():
                msg = make_msg(row)
                ts = dup.isoparse(msg[BrokerConstants.TIMESTAMP_KEY])
                if ts <= start or ts < window_start or ts > window_end or ts in seen:
                    continue
                if dry_run:
                    logger.info(f'Dry run: {mode} physical device {p_uid} at {ts.isoformat()}')
                else:
                    if processed and message_delay:
                        deadline = time.monotonic() + message_delay
                        while (remaining := deadline - time.monotonic()) > 0:
                            _connection.process_data_events(remaining)
                    process_msg(msg)
                seen.add(ts)
                processed += 1
        # Include the shared boundary in both requests; seen prevents duplicates.
        window_start = window_end

    if dry_run:
        logger.info(f'Dry run: {mode} would process {processed} messages for physical device {p_uid}')
    else:
        logger.info(f'{mode} processed {processed} messages for physical device {p_uid}')
    return processed


def parse_start_date(value: str) -> dt.datetime:
    try:
        ts = dup.isoparse(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('Use an ISO 8601 date or timestamp, such as 2025-01-01 or 2025-01-01T00:00:00+11:00.') from exc
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=_sydney_tz)
    return ts


def main() -> None:
    global _connection, _channel

    parser = argparse.ArgumentParser(description='Poll AxisTech, or query or load existing message timestamps for backfill.')
    parser.add_argument('--physical-device-id', type=int, help='Physical device ID to query or load timestamps for.')
    parser.add_argument('--start-date', type=parse_start_date,
                        help='Starting ISO 8601 date or timestamp. Dates without a timezone use Australia/Sydney.')
    parser.add_argument('--end-date', type=parse_start_date,
                        help='Required backfill end date or timestamp (inclusive), capped at the latest existing timestamp. '
                             'Forward fill uses this end date without the cap. Dates without a timezone use Australia/Sydney.')
    parser.add_argument('--forward-fill', action='store_true',
                        help='Process missing records through --end-date, including records newer than existing timestamps, then exit.')
    parser.add_argument('--message-delay', type=float,
                        help='Seconds between messages in forward-fill mode (default: 1; use 0 for no delay).')
    parser.add_argument('--load-timestamps', action='store_true',
                        help='Read <physical-device-id>.txt from the current directory instead of querying the database.')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview a backfill without publishing messages or changing database records or timestamp files.')
    args = parser.parse_args()
    if args.forward_fill and args.physical_device_id is None:
        parser.error('--forward-fill requires --physical-device-id, --start-date and --end-date')
    if args.message_delay is not None:
        if not args.forward_fill:
            parser.error('--message-delay requires --forward-fill')
        if not math.isfinite(args.message_delay) or args.message_delay < 0:
            parser.error('--message-delay must be a finite, non-negative number')
    if args.dry_run and args.physical_device_id is None:
        parser.error('--dry-run requires --physical-device-id and --start-date')
    if args.load_timestamps and args.physical_device_id is None:
        parser.error('--load-timestamps requires --physical-device-id and --start-date')
    if (args.physical_device_id is None) != (args.start_date is None):
        parser.error('--physical-device-id and --start-date must be supplied together')
    if args.end_date is not None and args.physical_device_id is None:
        parser.error('--end-date requires --physical-device-id and --start-date')
    if args.physical_device_id is not None:
        if args.end_date is None:
            parser.error('--end-date is required in backfill mode')
        if args.end_date <= args.start_date:
            parser.error('--end-date must be after --start-date')
        if args.physical_device_id < 1:
            parser.error('--physical-device-id must be a positive integer')
        if args.dry_run:
            try:
                existing_timestamps = get_msg_timestamps(args.physical_device_id, args.start_date,
                                                       load_timestamps=args.load_timestamps, save_timestamps=False)
                backfill_messages(args.physical_device_id, args.start_date, existing_timestamps,
                                  end=args.end_date, dry_run=True, forward_fill=args.forward_fill,
                                  message_delay=args.message_delay)
            finally:
                dao.stop()
            return
        logger.info('Forward-fill mode' if args.forward_fill else 'Backfill mode')
        existing_timestamps = get_msg_timestamps(args.physical_device_id, args.start_date,
                                               load_timestamps=args.load_timestamps)

    logger.info('===============================================================')
    logger.info('               STARTING AXISTECH POLLER')
    logger.info('===============================================================')

    dao.add_physical_source(BrokerConstants.AXISTECH)

    # Initialise the most recent message timestamp cache. This is used to control the time window
    # used in the AxisTech API calls.
    for pdev in dao.get_physical_devices_from_source(BrokerConstants.AXISTECH):
        if pdev.last_seen is not None:
            _recent_msg_times[pdev.source_ids['serial_no']] = pdev.last_seen

    try:
        logger.info('Opening connection')
        conn_attempts = 0
        backoff = 10
        while _connection is None:
            try:
                _connection = pika.BlockingConnection(pika.URLParameters(_amqp_url_str))
            except:
                conn_attempts += 1
                logger.warning(f'Connection to RabbitMQ attempt {conn_attempts} failed.')

                if conn_attempts % 5 == 0 and backoff < 60:
                    backoff += 10

                time.sleep(backoff)

        logger.info('Opening channel')
        _channel = _connection.channel()
        _channel.basic_qos(prefetch_count=1)
        logger.info('Declaring exchange')
        _channel.exchange_declare(exchange=BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME,
            exchange_type=ExchangeType.fanout, durable=True)

        if args.physical_device_id is not None:
            backfill_messages(args.physical_device_id, args.start_date, existing_timestamps, end=args.end_date,
                              forward_fill=args.forward_fill, message_delay=args.message_delay)
            return

        sleep_time = 1800 # seconds
        while True:
            poll()
            _connection.process_data_events(sleep_time)

    except KeyboardInterrupt:
        logger.info('Stopping')
    finally:
        dao.stop()

        if _connection is not None:
            _connection.close()


if __name__ == '__main__':
    main()
