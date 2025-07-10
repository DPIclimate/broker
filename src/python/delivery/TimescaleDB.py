"""
This program receives logical device timeseries messages and writes them into
the sensors table of the Timescale database.
"""

from typing import Any

# import dateutil.parser as dup

import logging, os, uuid

# import BrokerConstants

import util.LoggingUtil as lu

from delivery.BaseWriter import BaseWriter
from pdmodels.Models import LogicalDevice, PhysicalDevice

import psycopg2 as pg
from psycopg2.extras import execute_values

# import api.client.DAO as dao
from .intersect import wrangle

_conn = None

class TimescaleWriter(BaseWriter):
    def __init__(self) -> None:
        super().__init__('timescale')

    def on_message(self, pd: PhysicalDevice, ld: LogicalDevice, msg: dict[Any], retry_count: int) -> int:
        if _conn is None:
            logging.error('No connection.')
            return BaseWriter.MSG_FAIL

        try:
            # msg_uuid = uuid.UUID(msg[BrokerConstants.CORRELATION_ID_KEY])
            # msg_ts = dup.isoparse(msg['timestamp'])
            # p_uid = msg['p_uid']
            # l_uid = msg['l_uid']
            # location = dao.location_to_postgis_value(ld.location)
            # rows = []
            # for ts_obj in msg['timeseries']:
            #     try:
            #         name = ts_obj['name']
            #         value = ts_obj['value']
            #         if value is None:
            #             continue

            #         value = float(value)
            #         rows.append((msg_ts, msg_uuid, p_uid, l_uid, location, name, value))
            #     except ValueError as ve:
            #         pass

            intersect_rows = wrangle.wrangle(msg, _conn)

            # The db txn control must be done here because the entire script runs in the context of a psycopg2
            # connection; if the commit/rollback is not done here then the txn will never be committed.
            try:
                with _conn.cursor() as curs:
                    # execute_values(curs, 'insert into iota.measurement (ts, broker_correlation_id, puid, luid, location, name, value) values %s', rows)
                    execute_values(curs, 'insert into main.sensors (ts, broker_correlation_id, location_id, sensor_serial_id, position, variable, value, err_data) values %s', intersect_rows)
                    _conn.commit()
            except:
                _conn.rollback()
                lu.cid_logger.exception('Error writing to timescale database.', extra=msg)
                return BaseWriter.MSG_RETRY

            return BaseWriter.MSG_OK

        except BaseException:
            lu.cid_logger.exception('Error while processing message.', extra=msg)
            return BaseWriter.MSG_FAIL


if __name__ == '__main__':
    logging.info('Connecting to Timescale DB.')
    try:
        with pg.connect(f"host={os.environ['TSHOST']} port={os.environ['TSPORT']} dbname={os.environ['TSDATABASE']} user={os.environ['TSUSER']} password={os.environ['TSPASSWORD']}") as conn:
            _conn = conn
            TimescaleWriter().run()
    finally:
        if _conn is not None:
            _conn.close()

    logging.info('Exiting.')
