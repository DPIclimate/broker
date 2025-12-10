"""
This program receives logical device timeseries messages and writes them into
the sensors table of the Timescale database.
"""

from typing import Any

import logging, os, time

import util.LoggingUtil as lu

from delivery.BaseWriter import BaseWriter
from pdmodels.Models import LogicalDevice, PhysicalDevice

import psycopg2 as pg
from psycopg2.extras import execute_values
from psycopg2 import pool

from .intersect import wrangle


class TimescaleWriter(BaseWriter):
    def __init__(self) -> None:
        super().__init__('timescale')
        self.conn_pool = None

    def on_message(self, pd: PhysicalDevice, ld: LogicalDevice, msg: dict[Any], retry_count: int) -> int:
        conn = None
        try:
            # Try lazy initialisation the connection pool to give the db as
            # much time as possible to start.
            if self.conn_pool is None:
                logging.info('Creating SCMN DB connection pool.')
                self.conn_pool = pool.ThreadedConnectionPool(1, 5, f"host={os.environ['TSHOST']} port={os.environ['TSPORT']} dbname={os.environ['TSDATABASE']} user={os.environ['TSUSER']} password={os.environ['TSPASSWORD']}")

            conn = self.conn_pool.getconn()
            conn.autocommit = False
        except pg.Error as err:
            lu.cid_logger.exception('Failed to get SCMN DB connection.', extra=msg)
            time.sleep(10)
            return BaseWriter.MSG_RETRY

        try:
            intersect_rows = wrangle.wrangle(msg, conn)
            try:
                with conn.cursor() as curs:
                    execute_values(curs, 'insert into main.sensors (ts, broker_correlation_id, location_id, sensor_serial_id, position, variable, value, err_data) values %s', intersect_rows)
                    conn.commit()
            except:
                try:
                    lu.cid_logger.exception('Error writing to SCMN DB.', extra=msg)
                    conn.rollback()
                    self.conn_pool.putconn(conn, close=True)
                    time.sleep(10)
                    return BaseWriter.MSG_RETRY
                except:
                    lu.cid_logger.exception('SCMN DB rollback failed.', extra=msg)
                    self.conn_pool.putconn(conn, close=True)
                    time.sleep(10)
                    return BaseWriter.MSG_RETRY

            self.conn_pool.putconn(conn)
            return BaseWriter.MSG_OK

        except BaseException:
            lu.cid_logger.exception('Error while processing message.', extra=msg)
            if conn is not None:
                self.conn_pool.putconn(conn, close=True)

        return BaseWriter.MSG_FAIL


if __name__ == '__main__':
    tsw = None
    try:
        tsw = TimescaleWriter()
        tsw.run()
    finally:
        if tsw is not None and tsw.conn_pool is not None:
            logging.info('Closing SCMN DB connection pool.')
            tsw.conn_pool.closeall()

    logging.info('Exiting.')
