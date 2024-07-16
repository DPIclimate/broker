import argparse as ap
import datetime as dt
import logging
import os
from typing import Any, List, Optional
import pandas as pd
import psycopg2 as pg

import LoggingUtil

def get_data_for_logical_device(l_uid: int, start_ts: Optional[dt.datetime] = None, end_ts: Optional[dt.datetime] = None) -> pd.DataFrame:
    qry = """
        SELECT logical_uid, physical_uid, ts, received_at, ts_delta, json_msg->'timeseries' AS ts_array FROM physical_timeseries
         WHERE logical_uid = %s
    """

    qry_args: List[Any] = [l_uid]

    if start_ts is not None:
        qry += ' AND ts >= %s'
        qry_args.append(start_ts)

    if end_ts is not None:
        qry += ' AND ts < %s'
        qry_args.append(end_ts)

    dataset = []
    with pg.connect() as conn, conn.cursor() as curs:
        curs.execute('SELECT name from logical_devices where uid = %s', (l_uid, ))
        if curs.rowcount != 1:      # If > 1, how?
            logging.error(f'Did not find a logical device with id {l_uid}')
            exit(1)

        dev_name: str = str(curs.fetchone()[0])
        dev_name = dev_name.replace(' ', '_')
        logging.info(f'Fetching data for {l_uid} / {dev_name}')

        logging.debug(qry)
        logging.debug(curs.mogrify(qry, qry_args))
        curs.execute(qry, qry_args)
        if curs.rowcount < 1:
            logging.info(f'No data for {l_uid} / {dev_name}')
            exit(0)

        while True:
            rows = curs.fetchmany(size=2000)
            print(f'fetched {len(rows)} rows')
            if len(rows) < 1:
                break

            for row in rows:
                dset_item = {'l_uid': row[0], 'p_uid': row[1], 'ts': row[2], 'received_at': row[3], 'ts_delta': row[4]}
                for ts_obj in row[5]:
                    dset_item[ts_obj['name']] = ts_obj['value']
                dataset.append(dset_item)

    df = pd.DataFrame(dataset)
    df.set_index(['l_uid', 'ts'], inplace=True)
    df.sort_index(level=0, sort_remaining=True, inplace=True, ascending=True)
    df.to_csv(f'{l_uid}_{dev_name}.csv')
    return df


_default_host = 'localhost'
_default_port = '5432'
_default_dbname = 'broker'  # This is an IoTa utility, so use the IoTa database name by default.
_default_user = 'postgres'

parser = ap.ArgumentParser(description='Extract data from the IoTa database')
parser.add_argument('-H', dest='host', help='host to connect to, default = localhost')
parser.add_argument('-p', dest='port', help='port number to connect to, default = 5432')
parser.add_argument('-d', dest='dbname', help='database name to connect to, default = broker')
parser.add_argument('-U', dest='user', help='User name to connect as, default = postgres')
parser.add_argument('-P', dest='password', help='password to connect with, prefer to set PGPASSWORD env var')
parser.add_argument('-l', dest='l_uid', type=int, help='logical device id')
parser.add_argument('-s', dest='start_time', type=dt.datetime.fromisoformat, help='earliest timestamp in ISO-8601 format (>=)')
parser.add_argument('-e', dest='end_time', type=dt.datetime.fromisoformat, help='latest timestamp in ISO-8601 format (<)')

args = parser.parse_args()

# Give precendence to command line args, fall back to env var value if it is set,
# finally, fall back to a default value.
_host = os.getenv('PGHOST', _default_host) if args.host is None else args.host
if _host is not None:
    os.environ['PGHOST'] = _host

_port = os.getenv('PGPORT', _default_port) if args.port is None else args.port
if _port is not None:
    os.environ['PGPORT'] = _port

_dbname = os.getenv('PGDATABASE', _default_dbname)if args.dbname is None else args.dbname
if _dbname is not None:
    os.environ['PGDATABASE'] = _dbname

_user = os.getenv('PGUSER', _default_user) if args.user is None else args.user
if _user is not None:
    os.environ['PGUSER'] = _user

_password = os.getenv('PGPASSWORD') if args.password is None else args.password
if _password is not None:
    os.environ['PGPASSWORD'] = _password

get_data_for_logical_device(args.l_uid, args.start_time, args.end_time)
