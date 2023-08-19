from fastapi import FastAPI
import psycopg2, os, sys

app = FastAPI()

tsdb_user = os.environ.get("TSDB_USER")
tsdb_pass = os.environ.get("TSDB_PASSWORD")
tsdb_host = os.environ.get("TSDB_HOST")
tsdb_port = os.environ.get("TSDB_PORT")
tsdb_db = os.environ.get("TSDB_DB")
tsdb_table = os.environ.get("TSDB_TABLE")
CONNECTION = f"postgres://{tsdb_user}:{tsdb_pass}@{tsdb_host}:{tsdb_port}/{tsdb_db}"


@app.get("/")
async def query_tsdb(query: str = f"SELECT * FROM {tsdb_table};"):
    with psycopg2.connect(CONNECTION) as conn:
        # query = f"SELECT * FROM {tsdb_table};"
        cursor = conn.cursor()
        try: 
            cursor.execute(query)
            conn.commit()
            result = cursor.fetchall()
        except psycopg2.errors as e:
            sys.stderr.write(f'error: {e}\n')
        cursor.close()
    
    with open("test.txt", "w") as f:
        f.write(str(result))

    return {"title": result}

@app.get("/l_uid/{l_uid}")
async def get_luid_records(l_uid, fromdate = "", todate = "", p_uid = ""):
    with psycopg2.connect(CONNECTION) as conn:
        query = f"SELECT * FROM {tsdb_table} WHERE l_uid = '{l_uid}'"
        if fromdate != "":
            query += f"AND timestamp > '{fromdate}'"
        if todate != "":
            query += f"AND timestamp < '{todate}'"
        if p_uid != "":
            query += f"AND p_uid = '{p_uid}'"
        cursor = conn.cursor()
        try: 
            cursor.execute(query)
            conn.commit()
            result = cursor.fetchall()
        except psycopg2.errors as e:
            sys.stderr.write(f'error: {e}\n')
        cursor.close()    
    
    return result


@app.get("/p_uid/{p_uid}")
async def get_puid_records(p_uid: str, fromdate = "", todate = "", l_uid = ""):
    with psycopg2.connect(CONNECTION) as conn:
        query = f"SELECT * FROM {tsdb_table} WHERE p_uid = '{p_uid}'"
        if fromdate != "":
            query += f"AND timestamp > '{fromdate}'"
        if todate != "":
            query += f"AND timestamp < '{todate}'"
        if l_uid != "":
            query += f"AND l_uid = '{l_uid}'"
        cursor = conn.cursor()
        try: 
            cursor.execute(query)
            conn.commit()
            result = cursor.fetchall()
        except psycopg2.errors as e:
            sys.stderr.write(f'error: {e}\n')
        cursor.close()    
    
    return result

@app.get("/p_uid/{p_uid}/{func}")
async def get_puid_records(p_uid: str, func: str, fromdate = "", todate = "", l_uid = ""):
    with psycopg2.connect(CONNECTION) as conn:
        query = f"SELECT {func}({p_uid}) FROM {tsdb_table} WHERE p_uid = '{p_uid}'"
        if fromdate != "":
            query += f"AND timestamp > '{fromdate}'"
        if todate != "":
            query += f"AND timestamp < '{todate}'"
        if l_uid != "":
            query += f"AND l_uid = '{l_uid}'"
        cursor = conn.cursor()
        try: 
            cursor.execute(query)
            conn.commit()
            result = cursor.fetchall()
        except psycopg2.errors as e:
            sys.stderr.write(f'error: {e}\n')
        cursor.close()    
    
    return result