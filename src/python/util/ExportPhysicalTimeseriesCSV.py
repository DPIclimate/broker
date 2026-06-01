import argparse
import csv
import datetime as dt
import sys
from typing import TextIO

import dateutil.parser
import dateutil.tz


CSV_FIELDNAMES = ['l_uid', 'p_uid', 'msg_timestamp', 'timestamp', 'name', 'value']


def parse_aware_datetime(value: str) -> dt.datetime:
    """
    Parse an ISO-8601 timestamp and apply local timezone when none is present.

    Args:
        value: Timestamp text in ISO-8601 format.

    Returns:
        A timezone-aware datetime.
    """
    try:
        parsed = dateutil.parser.isoparse(value)
    except ValueError as err:
        raise argparse.ArgumentTypeError(f'Invalid datetime: {value}') from err

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=dateutil.tz.tzlocal())

    return parsed


def export_physical_timeseries_csv(
    logical_uid: int,
    start_date: dt.datetime,
    end_date: dt.datetime | None = None,
    output_file: TextIO | None = None,
) -> None:
    """
    Export physical_timeseries JSON timeseries entries to CSV for a logical device.

    Args:
        logical_uid: logical_uid value to select from physical_timeseries.
        start_date: Timezone-aware datetime whose calendar date is the inclusive first day.
        end_date: Optional timezone-aware datetime whose calendar date is the inclusive last day.
        output_file: Open text file to write CSV into, or None to write to stdout.

    Returns:
        None.
    """
    try:
        import psycopg2
    except ModuleNotFoundError as exc:
        raise SystemExit('Missing dependency: psycopg2. Install with: pip install psycopg2') from exc

    if start_date.tzinfo is None or start_date.utcoffset() is None:
        raise ValueError('start_date must include timezone information.')
    if end_date is not None and (end_date.tzinfo is None or end_date.utcoffset() is None):
        raise ValueError('end_date must include timezone information.')

    if output_file is None:
        output_file = sys.stdout

    start_bound = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_source = start_date if end_date is None else end_date
    end_bound = end_source.replace(hour=0, minute=0, second=0, microsecond=0) + dt.timedelta(days=1)

    if end_bound <= start_bound:
        raise ValueError('end_date must be on or after start_date.')

    writer = csv.DictWriter(output_file, fieldnames=CSV_FIELDNAMES)
    writer.writeheader()

    query = """
        SELECT uid, logical_uid, physical_uid, ts, json_msg
          FROM physical_timeseries
         WHERE logical_uid = %s
           AND ts >= %s
           AND ts < %s
         ORDER BY ts ASC, uid ASC
    """

    with psycopg2.connect() as conn, conn.cursor() as cursor:
        cursor.execute(query, (logical_uid, start_bound, end_bound))

        while True:
            rows = cursor.fetchmany(size=2000)
            if len(rows) < 1:
                break

            for uid, row_logical_uid, row_physical_uid, _row_ts, json_msg in rows:
                if not isinstance(json_msg, dict):
                    raise RuntimeError(f'physical_timeseries uid {uid} json_msg is not an object.')

                msg_timestamp = json_msg['timestamp']
                timeseries = json_msg['timeseries']
                if not isinstance(timeseries, list):
                    raise RuntimeError(f'physical_timeseries uid {uid} json_msg.timeseries is not an array.')

                for item in timeseries:
                    if not isinstance(item, dict):
                        raise RuntimeError(f'physical_timeseries uid {uid} timeseries entry is not an object.')

                    writer.writerow(
                        {
                            'l_uid': row_logical_uid,
                            'p_uid': row_physical_uid,
                            'msg_timestamp': msg_timestamp,
                            'timestamp': item.get('timestamp', msg_timestamp),
                            'name': item['name'],
                            'value': item['value'],
                        }
                    )


def build_parser() -> argparse.ArgumentParser:
    """
    Build the command line argument parser.

    Args:
        None.

    Returns:
        Configured argparse parser.
    """
    parser = argparse.ArgumentParser(
        description='Export physical_timeseries JSON timeseries entries to CSV for a logical device.'
    )
    parser.add_argument('l_uid', type=int, help='logical_uid to export.')
    parser.add_argument(
        'start_date',
        type=parse_aware_datetime,
        help='Start date as an ISO-8601 datetime. Naive values use the local timezone. Only the date part is used.',
    )
    parser.add_argument(
        'end_date',
        nargs='?',
        type=parse_aware_datetime,
        help='Optional end date as an ISO-8601 datetime. Naive values use the local timezone. Only the date part is used.',
    )
    parser.add_argument('-o', '--output', help='Optional output CSV filename. Defaults to stdout.')
    return parser


def main() -> None:
    """
    Parse command line arguments and run the CSV export.

    Args:
        None.

    Returns:
        None.
    """
    parser = build_parser()
    args = parser.parse_args()

    if args.output is None:
        export_physical_timeseries_csv(args.logical_uid, args.start_date, args.end_date)
        return

    with open(args.output, 'w', newline='', encoding='utf-8') as output_file:
        export_physical_timeseries_csv(args.l_uid, args.start_date, args.end_date, output_file)


if __name__ == '__main__':
    main()
