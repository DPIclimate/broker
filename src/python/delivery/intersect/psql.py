#  dpi-scmn-updateLookupTables psql.py
#  Description:      File containing functions for postgresql for project to write data into lookup tables from google sheets
#  Author:           Glen Charlton
#  Created:          11 April 2023
#  Source:           https://github.com/glencharlton/dpi-scmn-lookuptableupload/
#  License:          Copyright (c) 2020 Intersect Australia - All Rights Reserved
#                    Unauthorized copying of this file, via any medium is
#                    strictly prohibited. Proprietary and confidential

import psycopg2 as pg
import pandas as pd

##### function for connecting to psql database #####
def psql_connect():
    try:
        connection = pg.connect() # Use PG* env vars.
        return connection
    except pg.OperationalError as e:
        print("Error connecting to the database: ", e)
        return None

##### function for disconnecting from database #####
def psql_disconnect(connection):
    connection.close()

##### function for selecting data from table within the database #####
def psql_select_raw(connection, table_name, broker_correlation_id):
    try:
        query = "SELECT * FROM {} WHERE broker_correlation_id = '{}'".format(table_name, broker_correlation_id)
        df = pd.read_sql(query, connection)
        return df
    except pg.Error as e:
        print("Error executing the query: ", e)
        return None

##### function for inserting dataframe into database table #####
def psql_insert(connection, df, table_name):
    try:
        cursor = connection.cursor()
        column_names = ', '.join(df.columns)
        values = ', '.join(["%s" for _ in df.columns])
        query = "INSERT INTO {} ({}) VALUES ({})".format(table_name, column_names, values)
        cursor.executemany(query, [tuple(row) for row in df.to_numpy()])
        connection.commit()
    except pg.Error as e:
        print("Error inserting the data: ", e)
        connection.rollback()

##### function for replacing data within a table from a pandas dataframe #####
def psql_replace(connection, df, table_name):
    try:
        #clear table
        cursor = connection.cursor()
        query = "DELETE FROM {} ".format(table_name)
        cursor.execute(query)
        connection.commit()
        # insert
        cursor = connection.cursor()
        column_names = ', '.join(df.columns)
        values = ', '.join(["%s" for _ in df.columns])
        query = "INSERT INTO {} ({}) VALUES ({})".format(table_name, column_names, values)
        cursor.executemany(query, [tuple(row) for row in df.to_numpy()])
        connection.commit()
    except pg.Error as e:
        print("Error inserting the data into table ", table_name, ": ", e)
        connection.rollback()
