import json, os, re
import psycopg2
from psycopg2 import pool
from psycopg2.extensions import adapt, register_adapter, AsIs

from typing import Dict, List

from pdmodels.Models import Location, PhysicalDevice

class DAOException(BaseException):
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

    raise psycopg2.InterfaceError("bad point representation: %r" % value)


host = os.getenv('POSTGRES_HOST')
port = int(os.getenv('POSTGRES_PORT'))
user = os.getenv('POSTGRES_USER')
password = os.getenv('POSTGRES_PASSWORD')
dbname = os.getenv('POSTGRES_DB')

conn_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, host=host, port=port, user=user, password=password, dbname=dbname)


def _get_connection():
    """
    Get a database connection. Uses environment variables to get the host/port/user/password/database name.
    print("Connecting to database...")
    host = os.getenv('POSTGRES_HOST')
    port = int(os.getenv('POSTGRES_PORT'))
    user = os.getenv('POSTGRES_USER')
    password = os.getenv('POSTGRES_PASSWORD')
    dbname = os.getenv('POSTGRES_DB')

    return psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)
    """
    conn = conn_pool.getconn()
    return conn


def free_conn(conn) -> None:
    """
    Return a connection to the pool.
    """
    conn_pool.putconn(conn)


def _register_location_adapters():
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


# Register the adapter functions before anything else in this module is called.
_register_location_adapters()


def _dict_from_row(result_metadata, row) -> list:
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
    sources = []
    with _get_connection() as conn, conn.cursor() as cursor:
        conn.autocommit = True
        cursor.execute('select * from sources order by source_name')
        for source_name in cursor.fetchall():
            sources.append(source_name[0])

    free_conn(conn)
    return sources


"""
Physical device CRUD methods

create table if not exists physical_devices (
    uid integer generated always as identity primary key,
    source_name text not null references sources,
    name text not null,
    location point,
    last_seen timestamptz,
    properties jsonb not null default '{}'
);
"""
def create_physical_device(device: PhysicalDevice) -> PhysicalDevice:
    dev_fields = vars(device)

    # psycopg2 will not convert the dict into a JSON string automatically.
    dev_fields['properties'] = json.dumps(dev_fields['properties'])

    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute("insert into physical_devices (source_name, name, location, last_seen, properties) values (%(source_name)s, %(name)s, %(location)s, %(last_seen)s, %(properties)s) returning uid", dev_fields)
        uid = cursor.fetchone()[0]
        print(f'insert returned uid = {uid}')
        dev = _get_physical_device(conn, uid)
        print(f'new device = {dev}')
        conn.commit()

    free_conn(conn)
    return dev


def _get_physical_device(conn, uid: int) -> PhysicalDevice:
    """
    Query for a physical device in the context of an existing transaction.

    Getting a device via a uid is commonly done by other operations either to check the
    device exists, or to get a copy of the device before it is modified or deleted.

    This method allows the query to be more lightweight in those circumstances.

    conn: a database connection
    uid: the uid of the device to get
    """
    with conn.cursor() as cursor:
        sql = 'select uid, source_name, name, location, last_seen, properties from physical_devices where uid = %s'
        cursor.execute(sql, (uid, ))
        row = cursor.fetchone()
        if row is not None:
            dfr = _dict_from_row(cursor.description, row)
            dev = PhysicalDevice.parse_obj(dfr)
            return dev

        return None


def get_physical_device(uid: int) -> PhysicalDevice:
    with _get_connection() as conn:
        conn.autocommit = True
        dev = _get_physical_device(conn, uid)

    free_conn(conn)
    return dev


def get_physical_devices(query_args = {}) -> List[PhysicalDevice]:
    with _get_connection() as conn, conn.cursor() as cursor:
        conn.autocommit = True

        sql = 'select uid, source_name, name, location, last_seen, properties from physical_devices'
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
                    clause = clause + f'properties ->> %({name})s = %({name}_val)s'
                    args[name] = name
                    args[f'{name}_val'] = val
                    add_and = True
                    sql = sql + clause

        cursor.execute(sql, args)
        devs = []
        cursor.arraysize = 200
        rows = cursor.fetchmany()
        while len(rows) > 0:
            #print(f'processing {len(rows)} rows.', flush=True)
            for r in rows:
                d = PhysicalDevice.parse_obj(_dict_from_row(cursor.description, r))
                devs.append(d)

            rows = cursor.fetchmany()

    free_conn(conn)
    return devs


def update_physical_device(uid: int, device: PhysicalDevice) -> PhysicalDevice:
    with _get_connection() as conn:
        current_device = _get_physical_device(conn, uid)
        if current_device is None:
            raise DAOException

    current_values = vars(current_device)

    update_list = []
    for name, val in vars(device).items():
        if name == 'uid':
            continue

        if val != current_values[name]:
            update_list.append((name, val))

    if len(update_list) < 1:
        print('No update to device')
        return device

    print(update_list)

    add_and = False
    sql = 'update physical_devices set '
    args = {}

    """
    Look into this syntax given we are building the query with arbitrary column names.

    cur.execute(sql.SQL("insert into %s values (%%s)") % [sql.Identifier("my_table")], [42])
    """
    for name, val in update_list:
        clause = ' and ' if add_and else ''
        clause = clause + f'{name} = %({name}_val)s'
        args[name] = name

        # psycopg2 will not convert the dict into a JSON string automatically.
        nval = val if name != 'properties' else json.dumps(val)
        args[f'{name}_val'] = nval
        add_and = True
        sql = sql + clause

    sql = sql + f' where uid = {uid}'

    #print(sql)
    #print(cursor.mogrify(sql, args))

    with conn.cursor() as cursor:
        cursor.execute(sql, args)

    updated_device = _get_physical_device(conn, uid)
    #print(f'updated device = {updated_device}')

    conn.commit()
    free_conn(conn)
    return updated_device


def delete_physical_device(uid: int) -> PhysicalDevice:
    with _get_connection() as conn:
        dev = _get_physical_device(conn, uid)
        if dev is None:
            raise DAOException

        with conn.cursor() as cursor:
            cursor.execute('delete from physical_devices where uid = %s', (uid, ))

    conn.commit()
    free_conn(conn)
    return dev
