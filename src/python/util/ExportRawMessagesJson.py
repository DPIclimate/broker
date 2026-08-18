#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import sys
from typing import Any


def parse_month(value: str) -> dt.date:
    """
    Parse a month value in YYYY-MM format.

    Args:
        value: Month text in YYYY-MM format.

    Returns:
        Date for the first day of the requested month.
    """
    try:
        return dt.datetime.strptime(value, '%Y-%m').date().replace(day=1)
    except ValueError as err:
        raise argparse.ArgumentTypeError(f'Invalid month: {value}. Use YYYY-MM.') from err


def export_raw_messages_json(
    output_path: str,
    chunk_size: int,
    application_id: str = 'salinity-ict-c4e',
    start_month: dt.date = dt.date(2021, 1, 1),
    end_month: dt.date = dt.date(2023, 8, 1),
) -> int:
    """
    Export matching raw_messages json_msg values to one JSON array file.

    Args:
        output_path: Path to the JSON file to write.
        chunk_size: Number of messages to fetch from Postgres per chunk.
        application_id: TTN application_id value to match inside json_msg.
        start_month: First calendar month to include.
        end_month: Last calendar month to include.

    Returns:
        Count of exported messages.
    """
    if chunk_size < 1:
        raise ValueError('chunk_size must be at least 1.')
    if end_month < start_month:
        raise ValueError('end_month must be on or after start_month.')

    try:
        import dateutil.tz
        import psycopg2
        from psycopg2.extras import Json
    except ModuleNotFoundError as exc:
        raise SystemExit(f'Missing dependency: {exc.name}.') from exc

    local_tz = dateutil.tz.tzlocal()
    contains_filter: dict[str, Any] = {
        'end_device_ids': {
            'application_ids': {
                'application_id': application_id,
            },
        },
    }
    query = """
        SELECT json_msg
          FROM raw_messages
         WHERE ts >= %s
           AND ts < %s
           AND json_msg @> %s::jsonb
         ORDER BY ts ASC, uid ASC
    """

    total_count = 0
    current_month = start_month

    with psycopg2.connect() as conn, open(output_path, 'w', encoding='utf-8') as output_file:
        output_file.write('[\n')
        is_first_message = True

        while current_month <= end_month:
            if current_month.month == 12:
                next_month = current_month.replace(year=current_month.year + 1, month=1)
            else:
                next_month = current_month.replace(month=current_month.month + 1)

            month_start = dt.datetime.combine(current_month, dt.time.min, tzinfo=local_tz)
            month_end = dt.datetime.combine(next_month, dt.time.min, tzinfo=local_tz)
            month_count = 0

            with conn.cursor(name=f'raw_messages_export_{current_month:%Y_%m}') as cursor:
                cursor.itersize = chunk_size
                cursor.execute(query, (month_start, month_end, Json(contains_filter)))

                while True:
                    rows = cursor.fetchmany(chunk_size)
                    if len(rows) < 1:
                        break

                    for row in rows:
                        if not is_first_message:
                            output_file.write(',\n')

                        json.dump(row[0], output_file, ensure_ascii=False, separators=(',', ':'))
                        is_first_message = False
                        month_count += 1
                        total_count += 1

            print(f'{current_month:%Y-%m}: exported {month_count} messages', file=sys.stderr)
            current_month = next_month

        output_file.write('\n]\n')

    return total_count


def build_parser() -> argparse.ArgumentParser:
    """
    Build the command line argument parser.

    Args:
        None.

    Returns:
        Configured argparse parser.
    """
    parser = argparse.ArgumentParser(
        description='Export matching raw_messages json_msg values to a JSON array file in chunks.'
    )
    parser.add_argument('-o', '--output', default='clyde.json', help='Output JSON filename. Default: clyde.json.')
    parser.add_argument(
        '-n',
        '--chunk-size',
        type=int,
        default=10000,
        help='Number of messages to fetch per chunk. Default: 10000.',
    )
    parser.add_argument(
        '--application-id',
        default='salinity-ict-c4e',
        help='TTN application_id to match in json_msg. Default: salinity-ict-c4e.',
    )
    parser.add_argument('--start-month', type=parse_month, default=dt.date(2021, 1, 1), help='First month, YYYY-MM.')
    parser.add_argument('--end-month', type=parse_month, default=dt.date(2023, 8, 1), help='Last month, YYYY-MM.')
    return parser


def main() -> None:
    """
    Parse command line arguments and export raw messages.

    Args:
        None.

    Returns:
        None.
    """
    parser = build_parser()
    args = parser.parse_args()
    count = export_raw_messages_json(
        output_path=args.output,
        chunk_size=args.chunk_size,
        application_id=args.application_id,
        start_month=args.start_month,
        end_month=args.end_month,
    )
    print(f'Exported {count} messages to {args.output}', file=sys.stderr)


if __name__ == '__main__':
    main()
