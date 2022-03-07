from datetime import datetime
import logging, re, warnings
from numbers import Integral
import psycopg2
from psycopg2 import pool
import psycopg2.errors
from psycopg2.extensions import register_adapter, AsIs
from psycopg2.extras import Json, register_uuid

from typing import Any, Dict, List, Optional, Union

from pdmodels.Models import DeviceNote, Location, LogicalDevice, PhysicalDevice, PhysicalToLogicalMapping

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
logger = logging.getLogger(__name__)

class DAOException(Exception):
    def __init__(self, msg: str = None, wrapped: Exception = None):
        self.msg: str = msg
        self.wrapped: Exception = wrapped

# This is raised in update methods when the entity to be updated does not exist.
class DAODeviceNotFound(DAOException):
    pass

# This is raised if Postgres raises a unique constraint exception. It is useful
# for the REST API to know this was the problem rather than some general database
# problem, and allows calling code to not have to examine the Postgres exception
# directly.
class DAOUniqeConstraintException(DAOException):
    pass


def adapt_location(location: Location):
    """
    Transform a Location instance into a value usable in an SQL statement.
    """
    return AsIs(f"('{location.lat},{location.long}')")


def cast_point(value, cur):
    """
    Transform a value from an SQL result into a Location instance.
    """
    if value is None:
        return None

    if isinstance(value, str):
        m = re.fullmatch(r'\(([+-]?\d+\.?\d*),([+-]?\d+\.?\d*)\)', value)
        if m is not None:
            return Location(lat=float(m.group(1)),long=m.group(2))

    raise psycopg2.InterfaceError(f'Bad point representation: {value}')


conn_pool = None


def stop() -> None:
    logger.info('Closing connection pool.')
    conn_pool.closeall()


def _get_connection():
    global conn_pool

    # This throws an exception if the db hostname cannot be resolved, or
    # the database is not accepting connections.
    try:
        # Try lazy initialisation the connection pool and Location/point
        # converter to give the db as much time as possible to start.
        if conn_pool is None:
            logger.info('Creating connection pool, registering type converters.')
            conn_pool = pool.ThreadedConnectionPool(1, 5)
            _register_type_adapters()

        conn = conn_pool.getconn()
        logger.debug(f'Taking conn {conn}')
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

    logger.debug(f'Returning conn {conn}')
    if conn.closed == 0:
        conn.autocommit = False

    conn_pool.putconn(conn)


def _register_type_adapters():
    """
    Register adapter functions to handle Location <-> SQL Point data types.
    """
    # Apapter to convert from a Location instance to a quoted SQL string.
    register_adapter(Location, adapt_location)

    # Adapter to convert from an SQL result to a Location instance.
    with _get_connection() as conn, conn.cursor() as cursor:
        conn.autocommit = True
        cursor.execute("SELECT NULL::point")
        point_oid = cursor.description[0][1]
        POINT = psycopg2.extensions.new_type((point_oid,), "POINT", cast_point)
        psycopg2.extensions.register_type(POINT)

    free_conn(conn)
    register_uuid()


def _dict_from_row(result_metadata, row) -> Dict[str, Any]:
    obj = {}
    for i, col_def in enumerate(result_metadata):
        obj[col_def[0]] = row[i]

    return obj


"""
Physical device source CRUD methods

create table if not exists sources (
    source_name text primary key not null
);
"""
def get_all_physical_sources() -> List[PhysicalDevice]:
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
        free_conn(conn)


"""
Physical device CRUD methods
"""
def create_physical_device(device: PhysicalDevice) -> PhysicalDevice:
    try:
        dev_fields = {}
        for k, v in vars(device).items():
            dev_fields[k] = v if k not in ('source_ids', 'properties') else Json(v)

        with _get_connection() as conn, conn.cursor() as cursor:
            #logger.info(cursor.mogrify("insert into physical_devices (source_name, name, location, last_seen, source_ids, properties) values (%(source_name)s, %(name)s, %(location)s, %(last_seen)s, %(source_ids)s, %(properties)s) returning uid", dev_fields))
            cursor.execute("insert into physical_devices (source_name, name, location, last_seen, source_ids, properties) values (%(source_name)s, %(name)s, %(location)s, %(last_seen)s, %(source_ids)s, %(properties)s) returning uid", dev_fields)
            uid = cursor.fetchone()[0]
            dev = _get_physical_device(conn, uid)

        return dev
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('create_physical_device failed.', err)
    finally:
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
        sql = 'select uid, source_name, name, location, last_seen, source_ids, properties from physical_devices where uid = %s'
        cursor.execute(sql, (uid, ))
        row = cursor.fetchone()
        if row is not None:
            dfr = _dict_from_row(cursor.description, row)
            dev = PhysicalDevice.parse_obj(dfr)

    return dev


def get_physical_device(uid: int) -> PhysicalDevice:
    conn = None
    try:
        dev = None
        with _get_connection() as conn:
            dev = _get_physical_device(conn, uid)

        return dev
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_physical_device failed.', err)
    finally:
        free_conn(conn)


def get_pyhsical_devices_using_source_ids(source_name: str, source_ids: Dict[str, str]) -> List[PhysicalDevice]:
    try:
        devs = []
        with _get_connection() as conn, conn.cursor() as cursor:
            sql = 'select uid, source_name, name, location, last_seen, source_ids, properties from physical_devices where source_name = %s and source_ids @> %s order by uid asc'
            args = (source_name, Json(source_ids))
            #logger.info(cursor.mogrify(sql, args))
            cursor.execute(sql, args)
            for r in cursor:
                dfr = _dict_from_row(cursor.description, r)
                devs.append(PhysicalDevice.parse_obj(dfr))

        return devs
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_pyhsical_devices_using_source_ids failed.', err)
    finally:
        free_conn(conn)


def get_physical_devices(query_args = {}) -> List[PhysicalDevice]:
    try:
        devs = []
        with _get_connection() as conn, conn.cursor() as cursor:
            sql = 'select uid, source_name, name, location, last_seen, source_ids, properties from physical_devices'
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

            #logger.info(cursor.mogrify(sql, args))

            cursor.execute(sql, args)
            devs = []
            cursor.arraysize = 200
            rows = cursor.fetchmany()
            while len(rows) > 0:
                #logger.info(f'processing {len(rows)} rows.')
                for r in rows:
                    d = PhysicalDevice.parse_obj(_dict_from_row(cursor.description, r))
                    devs.append(d)

                rows = cursor.fetchmany()
        
        return devs
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_physical_devices failed.', err)
    finally:
        free_conn(conn)


def update_physical_device(device: PhysicalDevice) -> PhysicalDevice:
    try:
        with _get_connection() as conn:
            updated_device = _get_physical_device(conn, device.uid)
            if updated_device is None:
                raise DAODeviceNotFound(f'update_physical_device: device not found: {device.uid}')

            current_values = vars(updated_device)

            update_col_names = []
            update_col_values = []
            for name, val in vars(device).items():
                if val != current_values[name]:
                    update_col_names.append(f'{name} = %s')
                    update_col_values.append(val if name not in ('source_ids', 'properties') else Json(val))

            logger.debug(update_col_names)
            logger.debug(update_col_values)

            if len(update_col_names) < 1:
                return device

            update_col_values.append(device.uid)

            sql = f'''update physical_devices set {','.join(update_col_names)} where uid = %s'''

            """
            Look into this syntax given we are building the query with arbitrary column names.
            cur.execute(sql.SQL("insert into %s values (%%s)") % [sql.Identifier("my_table")], [42])
            """

            with conn.cursor() as cursor:
                logger.debug(cursor.mogrify(sql, update_col_values))
                cursor.execute(sql, update_col_values)

            return _get_physical_device(conn, device.uid)
    except DAODeviceNotFound as daonf:
        raise daonf
    except Exception as err:
        print(err)
        raise err if isinstance(err, DAOException) else DAOException('update_physical_device failed.', err)
    finally:
        free_conn(conn)


def delete_physical_device(uid: int) -> PhysicalDevice:
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
        free_conn(conn)


def create_physical_device_note(uid: int, note: str) -> None:
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute('insert into device_notes (physical_uid, note) values (%s, %s)', [uid, note])
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('create_physical_device_note failed.', err)
    finally:
        free_conn(conn)


def get_physical_device_notes(uid: int) -> List[DeviceNote]:
    try:
        notes = []
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute('select ts, note from device_notes where physical_uid = %s order by ts asc', [uid])
            for ts, note in cursor:
                notes.append(DeviceNote(ts=ts, note=note))

        return notes
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('create_physical_device_note failed.', err)
    finally:
        free_conn(conn)


"""
Logical Device CRUD methods
"""

def create_logical_device(device: LogicalDevice) -> LogicalDevice:
    try:
        dev = None
        dev_fields = {}
        for k, v in vars(device).items():
            dev_fields[k] = v if k != 'properties' else Json(v)

        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("insert into logical_devices (name, location, last_seen, properties) values (%(name)s, %(location)s, %(last_seen)s, %(properties)s) returning uid", dev_fields)
            uid = cursor.fetchone()[0]
            dev = _get_logical_device(conn, uid)

        return dev
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('create_logical_device failed.', err)
    finally:
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
        sql = 'select uid, name, location, last_seen, properties from logical_devices where uid = %s'
        cursor.execute(sql, (uid, ))
        row = cursor.fetchone()
        if row is not None:
            dfr = _dict_from_row(cursor.description, row)
            dev = LogicalDevice.parse_obj(dfr)

    return dev


def get_logical_device(uid: int) -> LogicalDevice:
    try:
        with _get_connection() as conn:
            dev = _get_logical_device(conn, uid)
            return dev
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_logical_device failed.', err)
    finally:
        free_conn(conn)


def get_logical_devices(query_args = {}) -> List[LogicalDevice]:
    try:
        devs = []
        with _get_connection() as conn, conn.cursor() as cursor:
            #conn.autocommit = True

            sql = 'select uid, name, location, last_seen, properties from logical_devices'
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

            #logger.info(cursor.mogrify(sql, args))

            cursor.execute(sql, args)
            cursor.arraysize = 200
            rows = cursor.fetchmany()
            while len(rows) > 0:
                #logger.info(f'processing {len(rows)} rows.')
                for r in rows:
                    d = LogicalDevice.parse_obj(_dict_from_row(cursor.description, r))
                    devs.append(d)

                rows = cursor.fetchmany()

        return devs
    except Exception as err:
        raise DAOException('get_logical_devices failed.', err)
    finally:
        free_conn(conn)


def update_logical_device(device: LogicalDevice) -> LogicalDevice:
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
                    update_col_values.append(val if name != 'properties' else Json(val))

            if len(update_col_names) < 1:
                return device

            update_col_values.append(device.uid)

            sql = f'''update logical_devices set {','.join(update_col_names)} where uid = %s'''

            with conn.cursor() as cursor:
                logger.debug(cursor.mogrify(sql, update_col_values))
                cursor.execute(sql, update_col_values)

            updated_device = _get_logical_device(conn, device.uid)
            return updated_device
    except DAODeviceNotFound as daonf:
        raise daonf
    except Exception as err:
        raise err if isinstance(err, DAOException) else DAOException('get_logical_device failed.', err)
    finally:
        free_conn(conn)


def delete_logical_device(uid: int) -> LogicalDevice:
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
        free_conn(conn)


"""
Physical to logical device mapping operations

create table if not exists physical_logical_map (
    physical_uid integer not null,
    logcial_uid integer not null,
    start_time timestamptz not null default now()
);

"""
def insert_mapping(mapping: PhysicalToLogicalMapping) -> None:
    """
    Insert a device mapping.
    """
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute('insert into physical_logical_map (physical_uid, logical_uid, start_time) values (%s, %s, %s)', (mapping.pd.uid, mapping.ld.uid, mapping.start_time))
    except psycopg2.errors.ForeignKeyViolation as fkerr:
        raise DAODeviceNotFound(f'insert_mapping foreign key error with mapping {mapping.pd.uid} -> {mapping.ld.uid}.', fkerr)
    except psycopg2.errors.UniqueViolation as err:
        raise DAOUniqeConstraintException(f'Mapping already exists: {mapping.pd.uid} -> {mapping.ld.uid}, starting at {mapping.start_time}.', err)
    except Exception as err:
        print(type(err), err)
        raise DAOException('insert_mapping failed.', err)
    finally:
        free_conn(conn)


def get_current_device_mapping(pd: Optional[Union[PhysicalDevice, Integral]] = None, ld: Optional[Union[LogicalDevice, Integral]] = None) -> Optional[PhysicalToLogicalMapping]:
    mapping = None

    if pd is None and ld is None:
        raise DAOException('A PhysicalDevice or a LogicalDevice (or an uid for one of them) must be supplied to find a mapping.')

    if pd is not None and ld is not None:
        raise DAOException('Both pd and ld were provided, only give one.')

    p_uid = None
    if pd is not None:
        p_uid = pd.uid if isinstance(pd, PhysicalDevice) else pd

    l_uid = None
    if ld is not None:
        l_uid = ld.uid if isinstance(ld, LogicalDevice) else ld

    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            conn.autocommit = True

            # A single query could get the data from all three tables but it would be unreadable.

            if p_uid is not None:
                cursor.execute('select physical_uid, logical_uid, start_time from physical_logical_map where physical_uid = %s order by start_time desc limit 1', (p_uid, ))
            else:
                cursor.execute('select physical_uid, logical_uid, start_time from physical_logical_map where logical_uid = %s order by start_time desc limit 1', (l_uid, ))

            if cursor.rowcount == 1:
                p_uid, l_uid, start_time = cursor.fetchone()

                pd = _get_physical_device(conn, p_uid)
                ld = _get_logical_device(conn, l_uid)

                mapping = PhysicalToLogicalMapping(pd=pd, ld=ld, start_time=start_time)

            return mapping

    except Exception as err:
        raise DAOException('get_current_device_mapping failed.', err)
    finally:
        free_conn(conn)


def add_raw_json_message(source_name: str, ts: datetime, correlation_uuid: str, msg, uid: int=None):
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute('insert into raw_messages (source_name, physical_uid, correlation_id, ts, json_msg) values (%s, %s, %s, %s, %s)', (source_name, uid, correlation_uuid, ts, Json(msg)))
    except psycopg2.errors.UniqueViolation as err:
        warnings.warn(f'Tried to add duplicate raw message: {source_name} {ts} {correlation_uuid} {msg}')
    except Exception as err:
        raise DAOException('add_raw_json_message failed.', err)
    finally:
        free_conn(conn)

def add_raw_text_message(source_name: str, ts: datetime, correlation_uuid: str, msg, uid: int=None):
    try:
        with _get_connection() as conn, conn.cursor() as cursor:
            cursor.execute('insert into raw_messages (source_name, physical_uid, correlation_id, ts, text_msg) values (%s, %s, %s, %s, %s)', (source_name, uid, correlation_uuid, ts, msg))
    except psycopg2.errors.UniqueViolation as err:
        warnings.warn(f'Tried to add duplicate raw message: {source_name} {ts} {correlation_uuid} {msg}')
    except Exception as err:
        raise DAOException('add_raw_text_message failed.', err)
    finally:
        free_conn(conn)
