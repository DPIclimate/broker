from contextlib import contextmanager
from datetime import datetime, timezone
import logging, warnings
import dateutil.parser
import psycopg2
from psycopg2 import pool
import psycopg2.errors
from psycopg2.extensions import AsIs
from psycopg2.extras import Json, register_uuid
from typing import Any, Dict, List, Optional, Tuple, Union
import hashlib
import os

import BrokerConstants
from pdmodels.Models import BaseDevice, DeviceNote, LogicalDevice, PhysicalDevice, PhysicalToLogicalMapping, User
from threading import Lock

logging.captureWarnings(True)

_lock = Lock()

class DAOException(Exception):
    def __init__(self, msg: str = None, wrapped: Exception = None):
        self.msg: str = msg
        self.wrapped: Exception = wrapped


# This is raised in update methods when the entity to be updated does not exist.
class DAODeviceNotFound(DAOException):
    pass


class DAOUserNotFound(DAOException):
    pass


# This is raised if Postgres raises a unique constraint exception. It is useful
# for the REST API to know this was the problem rather than some general database
# problem, and allows calling code to not have to examine the Postgres exception
# directly.
class DAOUniqeConstraintException(DAOException):
    pass


conn_pool = None
_physical_device_select_all_cols = """
select uid, source_name, name, (select row_to_json(_) from (select ST_Y(location) as lat, ST_X(location) as long) as _) as location, last_seen, source_ids, properties from physical_devices
"""

_logical_device_select_all_cols = """
select uid, name, (select row_to_json(_) from (select ST_Y(location) as lat, ST_X(location) as long) as _) as location, last_seen, properties from logical_devices
"""


_stopped = False

def stop() -> None:
    global _stopped
    logging.info('Closing connection pool.')
    _lock.acquire()
    try:
        if not _stopped:
            _stopped = True
            if conn_pool is not None:
                conn_pool.closeall()
    finally:
        _lock.release()


@contextmanager
def get_connection():
    logging.info('getting connection context')
    conn = _get_connection()
    try:
        yield conn
    finally:
        logging.info('freeing connection context')
        free_conn(conn)


def _get_connection():
    global conn_pool

    # This throws an exception if the db hostname cannot be resolved, or
    # the database is not accepting connections.
    try:
        # Try lazy initialisation the connection pool to give the db as
        # much time as possible to start.
        if conn_pool is None:
            logging.info('Creating connection pool, registering type converters.')
            conn_pool = pool.ThreadedConnectionPool(1, 5)
            register_uuid()

        conn = conn_pool.getconn()
        logging.debug(f'Taking conn {conn}')
        return conn
    except psycopg2.Error as err:
        raise DAOException('_get_connection() failed.', err)


def free_conn(conn) -> None:
    """
    Return a connection to the pool. Also sets autocommit to False.
    """
    global conn_pool

    if conn is None:
        return

    logging.debug(f'Returning conn {conn}')
    if conn.closed == 0 and conn.autocommit:
        conn.autocommit = False

    conn_pool.putconn(conn)


def _dict_from_row(result_metadata, row) -> Dict[str, Any]:
    obj = {}
    for i, col_def in enumerate(result_metadata):
        obj[col_def[0]] = row[i]

    return obj


def _device_to_query_params(device: BaseDevice) -> dict:
    dev_fields = {}
    for k, v in vars(device).items():
        match k:
            case 'properties' | 'source_ids':
                dev_fields[k] = Json(v)
            case 'location':
                if device.location is None or device.location.lat is None or device.location.long is None:
                    dev_fields[k] = None
                else:
                    dev_fields[k] = AsIs(f"ST_GeomFromText('POINT({device.location.long} {device.location.lat})')")
            case _:
                dev_fields[k] = v

    return dev_fields


"""
Physical device source CRUD methods
"""


def get_all_physical_sources() -> List[PhysicalDevice]:
    conn = None
    try:
        sources = []
        with _get_connection() as conn, conn.cursor() as cursor:
            conn.autocommit = True
            cursor.execute('select * from sources order by source_name')
            for source_name in cursor.fetchall():
                sources.append(source_name[0])

        return sources
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_all_physical_sources failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def add_physical_source(name: str) -> None:
    """
    Add a new physical device source if it does not already exist.
    """
    conn = None
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            conn.autocommit = False
            cursor.execute('select source_name from sources where source_name = %s', (name, ))
            if cursor.rowcount == 0:
                cursor.execute("insert into sources values (%s)", (name, ))
                cursor.execute('select source_name from sources where source_name = %s', (name, ))
                if cursor.rowcount == 1:
                    logging.info(f'Added physical device source {name}')
                    conn.commit()
                else:
                    logging.error(f'Failed to add physical device source {name}')
                    conn.rollback()
    except Exception as err:
        conn.rollback()
        raise err if isinstance(err, DAOException) else DAOException('add_physical_source failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


"""
Physical device CRUD methods
"""
def create_physical_device(device: PhysicalDevice) -> PhysicalDevice:
    conn = None
    try:
        dev_fields = _device_to_query_params(device)
        with _get_connection() as conn, conn.cursor() as cursor:
            #logging.info(cursor.mogrify("insert into physical_devices (source_name, name, location, last_seen, source_ids, properties) values (%(source_name)s, %(name)s, %(location)s, %(last_seen)s, %(source_ids)s, %(properties)s) returning uid", dev_fields))
            cursor.execute("insert into physical_devices (source_name, name, location, last_seen, source_ids, properties) values (%(source_name)s, %(name)s, %(location)s, %(last_seen)s, %(source_ids)s, %(properties)s) returning uid", dev_fields)
            uid = cursor.fetchone()[0]
            dev = _get_physical_device(conn, uid)
            return dev
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('create_physical_device failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def _get_physical_device(conn, uid: int) -> PhysicalDevice:
    """
    Query for a physical device in the context of an existing transaction.

    Getting a device via a uid is commonly done by other operations either to check the
    device exists, or to get a copy of the device before it is modified or deleted.

    This method allows the query to be more lightweight in those circumstances.

    conn: a database connection
    uid: the uid of the device to get
    """
    dev = None
    with conn.cursor() as cursor:
        sql = f'{_physical_device_select_all_cols} where uid = %s'
        cursor.execute(sql, (uid, ))
        row = cursor.fetchone()
        if row is not None:
            dfr = _dict_from_row(cursor.description, row)
            dev = PhysicalDevice.parse_obj(dfr)

    return dev


def get_physical_device(uid: int) -> PhysicalDevice:
    conn = None
    try:
        with _get_connection() as conn:
            dev = _get_physical_device(conn, uid)
            return dev
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_physical_device failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def get_pyhsical_devices_using_source_ids(source_name: str, source_ids: Dict[str, str]) -> List[PhysicalDevice]:
    conn = None
    try:
        devs = []
        with _get_connection() as conn, conn.cursor() as cursor:
            sql = f'{_physical_device_select_all_cols} where source_name = %s and source_ids @> %s order by uid asc'
            args = (source_name, Json(source_ids))
            #logging.info(cursor.mogrify(sql, args))
            cursor.execute(sql, args)
            for r in cursor:
                dfr = _dict_from_row(cursor.description, r)
                devs.append(PhysicalDevice.parse_obj(dfr))

        return devs
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_pyhsical_devices_using_source_ids failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def get_all_physical_devices() -> List[PhysicalDevice]:
    conn = None
    try:
        devs = []
        with _get_connection() as conn, conn.cursor() as cursor:
            sql = f'{_physical_device_select_all_cols} order by uid asc'
            cursor.execute(sql)
            cursor.arraysize = 200
            rows = cursor.fetchmany()
            while len(rows) > 0:
                for r in rows:
                    d = PhysicalDevice.parse_obj(_dict_from_row(cursor.description, r))
                    devs.append(d)

                rows = cursor.fetchmany()

        return devs
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_all_physical_devices failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def get_physical_devices_from_source(source_name: str) -> List[PhysicalDevice]:
    conn = None
    try:
        devs = []
        with _get_connection() as conn, conn.cursor() as cursor:
            sql = f'{_physical_device_select_all_cols} where source_name = %s order by uid asc'
            cursor.execute(sql, (source_name, ))
            cursor.arraysize = 200
            rows = cursor.fetchmany()
            while len(rows) > 0:
                for r in rows:
                    d = PhysicalDevice.parse_obj(_dict_from_row(cursor.description, r))
                    devs.append(d)

                rows = cursor.fetchmany()

        return devs
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_all_physical_devices failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def get_physical_devices(query_args=None) -> List[PhysicalDevice]:
    if query_args is None:
        query_args = {}

    conn = None
    try:
        devs = []
        with _get_connection() as conn, conn.cursor() as cursor:
            sql = _physical_device_select_all_cols
            args = {}

            add_where = True
            add_and = False

            if 'source' in query_args and query_args['source'] is not None:
                sql = sql + ' where ' if add_where else ''
                sql = sql + 'source_name = %(source)s'
                args['source'] = query_args['source']
                add_and = True
                add_where = False

            # How badly could putting arbitrary property name/value pairs into the SQL go wrong?
            if 'prop_name' in query_args and 'prop_value' in query_args:
                pnames = query_args['prop_name']
                pvals = query_args['prop_value']

                if pnames is not None and pvals is not None and len(pnames) == len(pvals):
                    if add_where:
                        sql = sql + ' where '

                    for name, val in zip(pnames, pvals):
                        clause = ' and ' if add_and else ''
                        clause = clause + f"properties ->> '{name}' = %({name}_val)s"
                        args[f'{name}_val'] = val
                        add_and = True
                        sql = sql + clause

            sql = sql + ' order by uid asc'

            #logging.info(cursor.mogrify(sql, args))

            cursor.execute(sql, args)
            devs = []
            cursor.arraysize = 200
            rows = cursor.fetchmany()
            while len(rows) > 0:
                #logging.info(f'processing {len(rows)} rows.')
                for r in rows:
                    d = PhysicalDevice.parse_obj(_dict_from_row(cursor.description, r))
                    devs.append(d)

                rows = cursor.fetchmany()

        return devs
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_physical_devices failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def update_physical_device(device: PhysicalDevice) -> PhysicalDevice:
    conn = None
    try:
        with _get_connection() as conn:
            current_device = _get_physical_device(conn, device.uid)
            if current_device is None:
                raise DAODeviceNotFound(f'update_physical_device: device not found: {device.uid}')

            current_values = vars(current_device)

            update_col_names = []
            update_col_values = []
            for name, val in vars(device).items():
                if val != current_values[name]:
                    update_col_names.append(f'{name} = %s')
                    match name:
                        case 'location':
                            if val is not None:
                                val = AsIs(f"ST_PointFromText('POINT({val.long} {val.lat})')")

                            update_col_values.append(val)

                        case 'properties' | 'source_ids':
                            update_col_values.append(Json(val))

                        case _:
                            update_col_values.append(val)

            logging.debug(update_col_names)
            logging.debug(update_col_values)

            if len(update_col_names) < 1:
                return device

            update_col_values.append(device.uid)

            sql = f'''update physical_devices set {','.join(update_col_names)} where uid = %s'''

            """
            Look into this syntax given we are building the query with arbitrary column names.
            cur.execute(sql.SQL("insert into %s values (%%s)") % [sql.Identifier("my_table")], [42])
            """

            with conn.cursor() as cursor:
                logging.debug(cursor.mogrify(sql, update_col_values))
                cursor.execute(sql, update_col_values)

            return _get_physical_device(conn, device.uid)
    except DAODeviceNotFound as daonf:
        raise daonf
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('update_physical_device failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def delete_physical_device(uid: int) -> PhysicalDevice:
    conn = None
    try:
        with _get_connection() as conn:
            dev = _get_physical_device(conn, uid)
            if dev is not None:
                with conn.cursor() as cursor:
                    cursor.execute('delete from physical_devices where uid = %s', (uid, ))

        return dev
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('delete_physical_device failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def create_physical_device_note(uid: int, note: str) -> None:
    conn = None
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute('insert into device_notes (physical_uid, note) values (%s, %s)', [uid, note])
    except psycopg2.errors.ForeignKeyViolation as fkerr:
        raise DAODeviceNotFound(f'create_physical_device_note foreign key error for device {uid}.', fkerr)
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('create_physical_device_note failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def get_physical_device_notes(uid: int) -> List[DeviceNote]:
    conn = None
    try:
        notes = []
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute('select uid, ts, note from device_notes where physical_uid = %s order by ts asc', [uid])
            for uid, ts, note in cursor:
                notes.append(DeviceNote(uid=uid, ts=ts, note=note))

        return notes
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('create_physical_device_note failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def update_physical_device_note(note: DeviceNote) -> None:
    conn = None
    try:
        with _get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('update device_notes set ts = %s, note = %s where uid = %s', (note.ts, note.note, note.uid))
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('update_physical_device_note failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def delete_physical_device_note(uid: int) -> None:
    conn = None
    try:
        with _get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('delete from device_notes where uid = %s', (uid, ))

    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('delete_physical_device_note failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


"""
Logical Device CRUD methods
"""

def create_logical_device(device: LogicalDevice) -> LogicalDevice:
    conn = None
    try:
        dev_fields = _device_to_query_params(device)
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("insert into logical_devices (name, location, last_seen, properties) values (%(name)s, %(location)s, %(last_seen)s, %(properties)s) returning uid", dev_fields)
            uid = cursor.fetchone()[0]
            dev = _get_logical_device(conn, uid)
            return dev
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('create_logical_device failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def _get_logical_device(conn, uid: int) -> LogicalDevice:
    """
    Query for a logical device in the context of an existing transaction.

    Getting a device via a uid is commonly done by other operations either to check the
    device exists, or to get a copy of the device before it is modified or deleted.

    This method allows the query to be more lightweight in those circumstances.

    conn: a database connection
    uid: the uid of the device to get
    """
    dev = None
    with conn.cursor() as cursor:
        """
        See: https://dba.stackexchange.com/questions/27732/set-names-to-attributes-when-creating-json-with-row-to-json

        for an explanation of how to name the fields in a row_to_json call.

        Example query tested in psql:
        select uid, name, (select row_to_json(_) from (select ST_Y(location) as lat, ST_X(location) as long) as _) as location from logical_devices;
        """
        sql = f'{_logical_device_select_all_cols} where uid = %s'
        cursor.execute(sql, (uid, ))
        row = cursor.fetchone()
        if row is not None:
            dfr = _dict_from_row(cursor.description, row)
            dev = LogicalDevice.parse_obj(dfr)

    return dev


def get_logical_device(uid: int) -> LogicalDevice:
    conn = None
    try:
        with _get_connection() as conn:
            dev = _get_logical_device(conn, uid)
            return dev
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_logical_device failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def get_logical_devices(query_args = {}) -> List[LogicalDevice]:
    conn = None
    try:
        devs = []
        with _get_connection() as conn, conn.cursor() as cursor:
            sql = _logical_device_select_all_cols
            args = {}

            add_where = True
            add_and = False

            # How badly could putting arbitrary property name/value pairs into the SQL go wrong?
            if 'prop_name' in query_args and 'prop_value' in query_args:
                pnames = query_args['prop_name']
                pvals = query_args['prop_value']

                if pnames is not None and pvals is not None and len(pnames) == len(pvals):
                    if add_where:
                        sql = sql + ' where '

                    for name, val in zip(pnames, pvals):
                        clause = ' and ' if add_and else ''
                        clause = clause + f"properties ->> '{name}' = %({name}_val)s"
                        args[f'{name}_val'] = val
                        add_and = True
                        sql = sql + clause

            sql = sql + ' order by uid asc'

            #logging.info(cursor.mogrify(sql, args))
            logging.info(cursor.mogrify(sql, args))
            cursor.execute(sql, args)
            cursor.arraysize = 200
            rows = cursor.fetchmany()
            while len(rows) > 0:
                for r in rows:
                    d = LogicalDevice.parse_obj(_dict_from_row(cursor.description, r))
                    devs.append(d)

                rows = cursor.fetchmany()

        return devs
    except Exception as err:
        raise DAOException('get_logical_devices failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def update_logical_device(device: LogicalDevice) -> LogicalDevice:
    conn = None
    try:
        with _get_connection() as conn:
            current_device = _get_logical_device(conn, device.uid)
            if current_device is None:
                raise DAODeviceNotFound(f'update_logical_device: device {device.uid} not found.')

            current_values = vars(current_device)

            update_col_names = []
            update_col_values = []
            for name, val in vars(device).items():
                if val != current_values[name]:
                    update_col_names.append(f'{name} = %s')
                    match name:
                        case 'location':
                            if val is not None:
                                val = AsIs(f"ST_PointFromText('POINT({val.long} {val.lat})')")

                            update_col_values.append(val)

                        case 'properties':
                            update_col_values.append(Json(val))

                        case _:
                            update_col_values.append(val)

            if len(update_col_names) < 1:
                return device

            update_col_values.append(device.uid)

            sql = f'''update logical_devices set {','.join(update_col_names)} where uid = %s'''

            with conn.cursor() as cursor:
                logging.debug(cursor.mogrify(sql, update_col_values))
                cursor.execute(sql, update_col_values)

            updated_device = _get_logical_device(conn, device.uid)
            return updated_device
    except DAODeviceNotFound as daonf:
        raise daonf
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_logical_device failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def delete_logical_device(uid: int) -> LogicalDevice:
    conn = None
    try:
        with _get_connection() as conn:
            dev = _get_logical_device(conn, uid)
            if dev is not None:
                with conn.cursor() as cursor:
                    cursor.execute('delete from logical_devices where uid = %s', (uid, ))

        return dev
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('delete_logical_device failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


"""
Physical to logical device mapping operations

create table if not exists physical_logical_map (
    physical_uid integer not null,
    logcial_uid integer not null,
    start_time timestamptz not null default now(),
    end_time timestamptz
);

"""
def insert_mapping(mapping: PhysicalToLogicalMapping) -> None:
    """
    Insert a device mapping.
    """
    conn = None
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            current_mapping = _get_current_device_mapping(conn, pd=mapping.pd.uid)
            if current_mapping is not None:
                raise ValueError(f'insert_mapping failed: physical device {current_mapping.pd.uid} / "{current_mapping.pd.name}" is already mapped to logical device {current_mapping.ld.uid} / "{current_mapping.ld.name}"')

            current_mapping = _get_current_device_mapping(conn, ld=mapping.ld.uid)
            if current_mapping is not None:
                _end_mapping(conn, ld=mapping.ld.uid)

            cursor.execute('insert into physical_logical_map (physical_uid, logical_uid, start_time) values (%s, %s, %s)', (mapping.pd.uid, mapping.ld.uid, mapping.start_time))
    except psycopg2.errors.ForeignKeyViolation as fkerr:
        raise DAODeviceNotFound(f'insert_mapping foreign key error with mapping {mapping.pd.uid} {mapping.pd.name} -> {mapping.ld.uid} {mapping.ld.name}.', fkerr)
    except psycopg2.errors.UniqueViolation as err:
        raise DAOUniqeConstraintException(f'Mapping already exists: {mapping.pd.uid} {mapping.pd.name} -> {mapping.ld.uid} {mapping.ld.name}, starting at {mapping.start_time}.', err)
    except Exception as err:
        match err:
            case DAOException() | ValueError():
                raise err
            case _:
                raise DAOException('insert_mapping failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def end_mapping(pd: Optional[Union[PhysicalDevice, int]] = None, ld: Optional[Union[LogicalDevice, int]] = None) -> None:
    conn = None
    try:
        with _get_connection() as conn:
            _end_mapping(conn, pd, ld)
    except Exception as err:
        match err:
            case DAOException() | ValueError():
                raise err
            case _:
                raise DAOException('end_mapping failed.', err)

    finally:
        if conn is not None:
            free_conn(conn)


def _end_mapping(conn, pd: Optional[Union[PhysicalDevice, int]] = None, ld: Optional[Union[LogicalDevice, int]] = None) -> None:
    with conn.cursor() as cursor:
        mapping: PhysicalToLogicalMapping = _get_current_device_mapping(conn, pd, ld)
        if mapping is None:
            return

        if pd is None and ld is None:
            raise ValueError('A PhysicalDevice or a LogicalDevice (or an uid for one of them) must be supplied to end a mapping.')

        if pd is not None and ld is not None:
            raise ValueError('Both pd and ld were provided, only give one when ending a mapping.')

        p_uid = None
        if pd is not None:
            p_uid = pd.uid if isinstance(pd, PhysicalDevice) else pd

        l_uid = None
        if ld is not None:
            l_uid = ld.uid if isinstance(ld, LogicalDevice) else ld

        if p_uid is not None:
            cursor.execute('update physical_logical_map set end_time = now() where physical_uid = %s and end_time is null', (p_uid, ))
        else:
            cursor.execute('update physical_logical_map set end_time = now() where logical_uid = %s and end_time is null', (l_uid, ))

        if cursor.rowcount != 1:
            logging.warning(f'No mapping was updated during end_mapping for {pd.uid} {pd.name} -> {ld.uid} {ld.name}')


def delete_mapping(mapping: PhysicalToLogicalMapping) -> None:
    """
        Remove an entry from the physical_logical_map table. Advised to use end_mapping instead. This method should only be used when permanently deleting a physical or logical device from the database.
    """
    conn = None
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
             cursor.execute('delete from physical_logical_map where physical_uid = %s and logical_uid = %s', (mapping.pd.uid, mapping.ld.uid))

    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('delete_mapping failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def toggle_device_mapping(is_active: bool, pd: Optional[Union[PhysicalDevice, int]] = None, ld: Optional[Union[LogicalDevice, int]] = None) -> None:
    """
        Change the is_active column in the database
    """

    conn = None
    try:
        with _get_connection() as conn:
            _toggle_device_mapping(conn, is_active, pd, ld)
        return
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('toggle_device_mapping failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def _toggle_device_mapping(conn, is_active, pd: Optional[Union[PhysicalDevice, int]] = None, ld: Optional[Union[LogicalDevice, int]] = None):

    if pd is None and ld is None:
        raise ValueError('A PhysicalDevice or a LogicalDevice (or an uid for one of them) must be supplied to find a mapping.')

    if pd is not None and ld is not None:
        raise ValueError('Both pd and ld were provided, only give one.')

    p_uid = None
    if pd is not None:
        p_uid = pd.uid if isinstance(pd, PhysicalDevice) else pd

    l_uid = None
    if ld is not None:
        l_uid = ld.uid if isinstance(ld, LogicalDevice) else ld

    with conn.cursor() as cursor:
        column_name = 'physical_uid' if p_uid is not None else 'logical_uid'
        sql = f'update physical_logical_map set is_active = %s where {column_name} = %s'
        cursor.execute(sql, (is_active, p_uid if p_uid is not None else l_uid, ))

        return None


def get_current_device_mapping(pd: Optional[Union[PhysicalDevice, int]] = None, ld: Optional[Union[LogicalDevice, int]] = None, only_current_mapping: bool = True) -> Optional[PhysicalToLogicalMapping]:
    conn = None
    try:
        with _get_connection() as conn:
            mapping = _get_current_device_mapping(conn, pd, ld, only_current_mapping)
            return mapping
    except Exception as err:
        match err:
            case DAOException() | ValueError():
                raise err
            case _:
                raise DAOException('insert_mapping failed.', err)

    finally:
        if conn is not None:
            free_conn(conn)


def _get_current_device_mapping(conn, pd: Optional[Union[PhysicalDevice, int]] = None, ld: Optional[Union[LogicalDevice, int]] = None, only_current_mapping: bool = True) -> Optional[PhysicalToLogicalMapping]:
    mappings = None

    if pd is None and ld is None:
        raise ValueError('A PhysicalDevice or a LogicalDevice (or an uid for one of them) must be supplied to find a mapping.')

    if pd is not None and ld is not None:
        raise ValueError('Both pd and ld were provided, only give one.')

    p_uid = None
    if pd is not None:
        p_uid = pd.uid if isinstance(pd, PhysicalDevice) else pd

    l_uid = None
    if ld is not None:
        l_uid = ld.uid if isinstance(ld, LogicalDevice) else ld

    end_time_clause = 'and end_time is null' if only_current_mapping else ''

    with conn.cursor() as cursor:
        column_name = 'physical_uid' if p_uid is not None else 'logical_uid'
        sql = f'select physical_uid, logical_uid, start_time, end_time, is_active from physical_logical_map where {column_name} = %s {end_time_clause} order by start_time desc'
        cursor.execute(sql, (p_uid if p_uid is not None else l_uid, ))

        mappings = []
        for p_uid, l_uid, start_time, end_time, is_active in cursor:
            pd = _get_physical_device(conn, p_uid)
            ld = _get_logical_device(conn, l_uid)
            mappings.append(PhysicalToLogicalMapping(pd=pd, ld=ld, start_time=start_time, end_time=end_time, is_active=is_active))

        if only_current_mapping and len(mappings) > 1:
            warnings.warn(f'Found multiple ({cursor.rowcount}) current mappings for {pd.uid} {pd.name} -> {ld.uid} {ld.name}')
            for m in mappings:
                logging.warning(m)

        if len(mappings) > 0:
            return mappings[0]

        return None


def get_unmapped_physical_devices() -> List[PhysicalDevice]:
    conn = None
    try:
        devs = []
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(f'{_physical_device_select_all_cols} where uid not in (select physical_uid from physical_logical_map where end_time is null) order by uid asc')
            for r in cursor:
                dfr = _dict_from_row(cursor.description, r)
                devs.append(PhysicalDevice.parse_obj(dfr))

        return devs
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_unmapped_physical_devices failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def get_logical_device_mappings(ld: Union[LogicalDevice, int]) -> List[PhysicalToLogicalMapping]:
    conn = None
    try:
        mappings = []
        with _get_connection() as conn, conn.cursor() as cursor:
            l_uid = ld.uid if isinstance(ld, LogicalDevice) else ld
            cursor.execute('select physical_uid, logical_uid, start_time, end_time, is_active from physical_logical_map where logical_uid = %s order by start_time desc', (l_uid, ))
            for p_uid, l_uid, start_time, end_time, is_active in cursor:
                pd = _get_physical_device(conn, p_uid)
                ld = _get_logical_device(conn, l_uid)
                mapping = PhysicalToLogicalMapping(pd=pd, ld=ld, start_time=start_time, end_time=end_time, is_active=is_active)
                mappings.append(mapping)

        return mappings
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_logical_device_mappings failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def get_physical_device_mappings(pd: Union[PhysicalDevice, int]) -> List[PhysicalToLogicalMapping]:
    conn = None
    try:
        mappings = []
        with _get_connection() as conn, conn.cursor() as cursor:
            p_uid = pd.uid if isinstance(pd, PhysicalDevice) else pd
            cursor.execute('select physical_uid, logical_uid, start_time, end_time, is_active from physical_logical_map where physical_uid = %s order by start_time desc', (p_uid, ))

            for p_uid, l_uid, start_time, end_time, is_active in cursor:
                pd = _get_physical_device(conn, p_uid)
                ld = _get_logical_device(conn, l_uid)
                mapping = PhysicalToLogicalMapping(pd=pd, ld=ld, start_time=start_time, end_time=end_time, is_active=is_active)
                mappings.append(mapping)

        return mappings
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_physical_logical_mappings failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)

def get_all_current_mappings(return_uids: bool = True) -> List[PhysicalToLogicalMapping]:
    conn = None
    try:
        mappings = []
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute('select physical_uid, logical_uid, start_time, end_time, is_active from physical_logical_map where end_time is null order by logical_uid asc')
            for p_uid, l_uid, start_time, end_time, is_active in cursor:
                if return_uids:
                    pd = p_uid
                    ld = l_uid
                else:
                    pd = _get_physical_device(conn, p_uid)
                    ld = _get_logical_device(conn, l_uid)
                mapping = PhysicalToLogicalMapping(pd=pd, ld=ld, start_time=start_time, end_time=end_time, is_active=is_active)
                mappings.append(mapping)

        return mappings
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_all_current_mappings failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def add_raw_json_message(source_name: str, ts: datetime, correlation_uuid: str, msg, uid: int=None):
    conn = None
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute('insert into raw_messages (source_name, physical_uid, correlation_id, ts, json_msg) values (%s, %s, %s, %s, %s)', (source_name, uid, correlation_uuid, ts, Json(msg)))
    except psycopg2.errors.UniqueViolation as err:
        warnings.warn(f'Tried to add duplicate raw message: {source_name} {ts} {correlation_uuid} {msg}')
    except Exception as err:
        raise DAOException('add_raw_json_message failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def insert_physical_timeseries_message(msg: Dict[str, Any]) -> None:
    conn = None
    p_uid = msg[BrokerConstants.PHYSICAL_DEVICE_UID_KEY]
    l_uid = msg[BrokerConstants.LOGICAL_DEVICE_UID_KEY] if BrokerConstants.LOGICAL_DEVICE_UID_KEY in msg else None
    ts = msg[BrokerConstants.TIMESTAMP_KEY]

    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute('insert into physical_timeseries (physical_uid, ts, logical_uid, json_msg) values (%s, %s, %s, %s)', (p_uid, ts, l_uid, Json(msg)))
    except Exception as err:
        raise DAOException('insert_physical_timeseries_message failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def get_physical_timeseries_message(start: datetime | None = None, end: datetime | None = None, count: int | None = None, only_timestamp: bool = False, include_received_at: bool = False, p_uid: int = None, l_uid: int = None) -> List[Dict]:
    conn = None

    if start is None:
        start = dateutil.parser.isoparse('1970-01-01T00:00:00Z')
    if end is None:
        end = datetime.now(timezone.utc)
    if count is None or count > 65536:
        count = 65536 * 2
    if count < 1:
        count = 1

    if p_uid is None and l_uid is None:
        raise ValueError('p_uid or l_uid must be supplied.')

    if p_uid is not None and l_uid is not None:
        raise ValueError('Both p_uid and l_uid were provided, only give one.')

    if p_uid is not None:
        uid_col_name = 'physical_uid'
        uid = p_uid
    else:
        uid_col_name = 'logical_uid'
        uid = l_uid

    if not isinstance(uid, int):
        raise TypeError

    if not isinstance(start, datetime):
        raise TypeError

    if not isinstance(end, datetime):
        raise TypeError

    # NOTE: The value that comes out of date_trunc does not have a timezone attached, but is a timestamp of the correct
    # value in the UTC timezone. So the outer timezone() call makes it back into a timestamptz, with a timezone of UTC.
    column_names = ["timezone('UTC', date_trunc('second', ts at time zone 'UTC')) as ts_utc"]
    if include_received_at:
        column_names.append("timezone('UTC', date_trunc('second', received_at at time zone 'UTC')) as received_at_utc")

    if not only_timestamp:
        column_names.append('json_msg')

    column_names = ', '.join(column_names)

    try:
        # Order messages by descending timestamp. If a caller asks for one message, they probably want the latest
        # message.
        with _get_connection() as conn, conn.cursor() as cursor:
            qry = f"""
                select {column_names} from physical_timeseries
                 where {uid_col_name} = %s
                 and ts > %s
                 and ts <= %s
                 order by ts desc
                 limit %s
                """

            args = (uid, start, end, count)
            cursor.execute(qry, args)
            return [_msg_tuple_to_obj(cursor.description, row) for row in cursor.fetchall()]

    except Exception as err:
        raise DAOException('get_physical_timeseries_message failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def _msg_tuple_to_obj(cursor_description, values) -> dict:
    msg_dict = {}

    for k, v in zip(cursor_description, values):
        if isinstance(v, datetime):
            # This function expects naive datetime instances to represent the time in UTC.
            msg_dict[k.name] = v.astimezone(timezone.utc).isoformat()
        elif isinstance(v, dict):
            msg_dict.update(v)

    return msg_dict


def add_raw_text_message(source_name: str, ts: datetime, correlation_uuid: str, msg, uid: int=None):
    conn = None
    try:
        with _get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('insert into raw_messages (source_name, physical_uid, correlation_id, ts, text_msg) values (%s, %s, %s, %s, %s)', (source_name, uid, correlation_uuid, ts, msg))
    except psycopg2.errors.UniqueViolation as err:
        warnings.warn(f'Tried to add duplicate raw message: {source_name} {ts} {correlation_uuid} {msg}')
    except Exception as err:
        raise DAOException('add_raw_text_message failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


"""
User and authentication CRUD methods
"""
def user_add(uname: str, passwd: str, disabled: bool) -> None:

    #Generate salted password
    salt=os.urandom(64).hex()
    pass_hash=hashlib.scrypt(password=passwd.encode(), salt=salt.encode(), n=2**14, r=8, p=1, maxmem=0, dklen=64).hex()

    #Auth token to be used on other endpoints
    auth_token=os.urandom(64).hex()
    conn = None
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("insert into users (username, salt, password, auth_token, valid) values (%s, %s, %s, %s, %s)", (uname, salt, pass_hash, auth_token, not disabled))
            conn.commit()
    except psycopg2.errors.UniqueViolation as err:
        raise DAOUniqeConstraintException("Unique constraint violated")
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('add_user failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def user_rm(uname: str) -> None:
    conn = None
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("delete from users where username=%s", (uname,))

    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('user_ls failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def user_set_read_only(uname: str, read_only: bool) -> None:
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("update users set read_only=%s where username=%s", (read_only,uname))
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('user_enable_write failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def get_user(uid = None, username = None, auth_token = None) -> User:
    conn = None
    if uid is None and username is None and auth_token is None:
        raise ValueError('get_user requires at least one parameter')
    else:
        try:
            user = None
            with _get_connection() as conn, conn.cursor() as cursor:
                if uid is not None:
                    cursor.execute("select uid, username, auth_token, valid, read_only from users where uid=%s", (uid,))
                elif username is not None:
                    cursor.execute("select uid, username, auth_token, valid, read_only from users where username=%s", (username,))
                elif auth_token is not None:
                    cursor.execute("select uid, username, auth_token, valid, read_only from users where auth_token=%s", (auth_token,))
                row = cursor.fetchone()
                if row is not None:
                    dfr = _dict_from_row(cursor.description, row)
                    user = User.parse_obj(dfr)
            return user
        except Exception as err:
            raise err if isinstance(err, DAOException) else DAOException('get_user failed.', err)
        finally:
            if conn is not None:
                free_conn(conn)


def user_ls() -> List:
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("select username from users order by uid")
            results = cursor.fetchall()
            return [i[0] for i in results]

    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('user_ls failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def user_get_token(username, password) -> str | None:

    conn = None
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("select salt, password, auth_token from users where username=%s",(username,))
            result = cursor.fetchone()
            if result is None:
                return None

            db_salt, db_password, auth_token=result
            input_pw_hash=hashlib.scrypt(password=password.encode(), salt=db_salt.encode(), n=2**14, r=8, p=1, maxmem=0, dklen=64).hex()

            if input_pw_hash != db_password:
                #Incorrect password supplied
                return None

            return auth_token

    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_user_token failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def token_is_valid(user_token) -> bool:
    '''
    Check if token is in database and is valid
    '''
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("select uid from users where auth_token=%s and valid='True'", (user_token,))
            result = cursor.fetchone()

            if result is None:
                return False
            return True
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('is_valid_token failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def token_refresh(uname) -> None:

    # Auth token to be used on other endpoints.
    auth_token = os.urandom(64).hex()

    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("update users set auth_token=%s where username=%s", (auth_token, uname))
            conn.commit()

    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('token_refresh failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def user_change_password(username: str, new_passwd: str) -> None:
    salt = os.urandom(64).hex()
    pass_hash = hashlib.scrypt(password=new_passwd.encode(), salt=salt.encode(), n=2**14, r=8, p=1, maxmem=0, dklen=64).hex()

    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("update users set salt=%s, password=%s where username=%s", (salt, pass_hash, username))
            conn.commit()
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('user_change_passwd failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def user_change_password_and_token(new_passwd: str, prev_token: str) -> str:
    """
        Changes user's password and auth token, returns users new auth token upon success
    """
    #Generate salted password
    salt = os.urandom(64).hex()
    pass_hash = hashlib.scrypt(password=new_passwd.encode(), salt=salt.encode(), n=2**14, r=8, p=1, maxmem=0, dklen=64).hex()

    #Auth token to be used on other endpoints
    auth_token = os.urandom(64).hex()

    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("update users set salt=%s, password=%s, auth_token=%s where auth_token=%s", (salt, pass_hash, auth_token, prev_token))
            conn.commit()
            if cursor.rowcount == 0:
                return None

            return auth_token

    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('user_change_password_and_token failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def token_disable(uname) -> None:

    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("update users set valid='F' where username=%s", (uname,))

    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('disable_token failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


def token_enable(uname)-> None:
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("update users set valid='T' where username=%s", (uname,))

    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('disable_token failed.', err)
    finally:
        if conn is not None:
            free_conn(conn)


# ===========================================================================
# Delivery thread related functions
# ===========================================================================

def _get_delivery_table_id(name: str) -> str:
    #return sql.Identifier(f'{name}_delivery_q')
    return f'{name}_delivery_q'

def create_delivery_table(name: str) -> None:
    logging.info(f'Creating message delivery table for service {name}')

    try:
        qry = f"""create table if not exists {_get_delivery_table_id(name)} (
                    uid integer generated always as identity primary key,
                    json_msg jsonb not null,
                    retry_count integer not null default 0)"""

        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(qry)

    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('create_delivery_table failed.', err)
    finally:
        if conn is not None:
            conn.commit()
            free_conn(conn)

def get_delivery_msg_count(name: str) -> int:
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(f'select count(uid) from {_get_delivery_table_id(name)}')
            return cursor.fetchone()[0]

    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_delivery_msg_count failed.', err)
    finally:
        if conn is not None:
            conn.commit()
            free_conn(conn)

def get_delivery_msg_batch(name: str, from_uid: int = 0, batch_size: int = 10) -> List[Tuple[int, list[dict[Any]]]]:
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            # Using order by asc in case time series databases need values inserted in timestamp order.
            cursor.execute(f'select uid, json_msg, retry_count from {_get_delivery_table_id(name)} where uid > %s order by uid asc limit %s', (from_uid, batch_size))
            if cursor.rowcount < 1:
                return 0, []

            return cursor.fetchall()

    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_delivery_msg_batch failed.', err)
    finally:
        if conn is not None:
            conn.commit()
            free_conn(conn)

def add_delivery_msg(name: str, msg: dict[Any]) -> None:
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(f'insert into {_get_delivery_table_id(name)} (json_msg) values (%s)', (Json(msg), ))

    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('add_delivery_msg failed.', err)
    finally:
        if conn is not None:
            conn.commit()
            free_conn(conn)

def remove_delivery_msg(name: str, uid: int) -> None:
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(f'delete from {_get_delivery_table_id(name)} where uid = %s', (uid, ))

    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('remove_delivery_msg failed.', err)
    finally:
        if conn is not None:
            conn.commit()
            free_conn(conn)

def retry_delivery_msg(name: str, uid: int) -> None:
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(f'select retry_count from {_get_delivery_table_id(name)} where uid = %s', (uid, ))
            if cursor.rowcount < 1:
                return

            retry_count = cursor.fetchone()[0] + 1
            cursor.execute(f'update {_get_delivery_table_id(name)} set retry_count = %s where uid = %s', (retry_count, uid))

    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('retry_delivery_msg failed.', err)
    finally:
        if conn is not None:
            conn.commit()
            free_conn(conn)
