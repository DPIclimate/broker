import psycopg2
import os, sys

host = os.getenv('POSTGRES_HOST')
port = int(os.getenv('POSTGRES_PORT'))
user = os.getenv('POSTGRES_USER')
password = os.getenv('POSTGRES_PASSWORD')
dbname = os.getenv('POSTGRES_DB')

dev_name = sys.argv[-1]

with psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname) as conn:
    conn.autocommit = False
    with conn.cursor() as cursor:
        cursor.execute('select uid from physical_devices where name = %s', (dev_name, ))
        rs = cursor.fetchone()
        if rs is not None:
            print(rs)
            p_uid = rs[0]

            cursor.execute('select logical_uid from physical_logical_map where physical_uid = %s', (p_uid, ))
            rs = cursor.fetchone()
            if rs is not None:
                l_uid = rs[0]

                print(f'{p_uid} --> {l_uid}')

                cursor.execute('delete from physical_logical_map where physical_uid = %s', (p_uid, ))
                cursor.execute('delete from physical_devices where uid = %s', (p_uid, ))
                cursor.execute('delete from logical_devices where uid = %s', (l_uid, ))

    conn.commit()

conn.close()
