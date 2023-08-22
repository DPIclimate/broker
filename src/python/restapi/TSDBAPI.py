from fastapi import APIRouter
import psycopg2, os, sys, datetime

router = APIRouter(prefix="/query")

tsdb_user = os.environ.get("TSDB_USER")
tsdb_pass = os.environ.get("TSDB_PASSWORD")
tsdb_host = os.environ.get("TSDB_HOST")
tsdb_port = os.environ.get("TSDB_PORT")
tsdb_db = os.environ.get("TSDB_DB")
tsdb_table = os.environ.get("TSDB_TABLE")
CONNECTION = f"postgres://{tsdb_user}:{tsdb_pass}@{tsdb_host}:{tsdb_port}/{tsdb_db}"


@router.get("/")
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

@router.get("/l_uid/{l_uid}")
async def get_luid_records(l_uid, fromdate = "", todate = "", p_uid = ""):
    with psycopg2.connect(CONNECTION) as conn:
        query = f"SELECT * FROM {tsdb_table} WHERE l_uid = '{l_uid}'"
        if fromdate != "":
            query += f"AND timestamp >= '{fromdate}'"
        if todate != "":
            query += f"AND timestamp <= '{todate}'"
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


@router.get("/p_uid/{p_uid}")
async def get_puid_records(p_uid: str, fromdate = "", todate = "", l_uid = ""):
    with psycopg2.connect(CONNECTION) as conn:
        query = f"SELECT * FROM {tsdb_table} WHERE p_uid = '{p_uid}'"
        if fromdate != "":
            query += f"AND timestamp >= '{fromdate}'"
        if todate != "":
            query += f"AND timestamp <= '{todate}'"
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

@router.get("/p_uid/{p_uid}/{func}")
async def get_puid_records(p_uid: str, func: str, fromdate = "", todate = "", l_uid = ""):
    with psycopg2.connect(CONNECTION) as conn:
        query = f"SELECT {func}(value) FROM {tsdb_table} WHERE p_uid = '{p_uid}'"
        if fromdate != "":
            query += f"AND timestamp >= '{fromdate}'"
        if todate != "":
            query += f"AND timestamp <= '{todate}'"
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

@router.get("/l_uid/{l_uid}/last")
async def get_luid_for_last_x(l_uid: str, years = 0, months = 0, days = 0, hours = 0, minutes = 0, seconds = 0):
    with psycopg2.connect(CONNECTION) as conn:
        date = datetime.datetime.now()
        current_date = f"{date.year}-{date.month}-{date.day} {date.hour}:{date.minute}:{date.second}" 
        target_year = date.year - int(years)
        target_month = date.month - int(months)
        target_day = date.day - int(days)
        target_hour = date.hour - int(hours)
        target_minute = date.minute - int(minutes)
        target_second = date.second - float(seconds)
        while target_second < 0:
            target_second += 60
            target_minute -= 1
        while target_minute < 0:
            target_minute += 60
            target_hour -= 1
        while target_hour < 0:
            target_hour += 24
            target_day -= 1
        while target_day <= 0:
            target_day += 30
            target_month -= 1
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        if target_month == 2 and target_day > 28:
            target_month = 3
            target_day -= 28
        target_date = f"{target_year}-{target_month}-{target_day}"  
        query = f"SELECT * FROM {tsdb_table} WHERE l_uid = '{l_uid}'"
        query += f" AND timestamp <= '{current_date}'"
        query += f" AND timestamp >= '{target_date}'"
        cursor = conn.cursor()
        try: 
            cursor.execute(query)
            conn.commit()
            result = cursor.fetchall()
        except psycopg2.errors as e:
            sys.stderr.write(f'error: {e}\n')
        cursor.close()
    
    return result

@router.get("/p_uid/{p_uid}/last")
async def get_puid_for_last_x(p_uid: str, years = 0, months = 0, days = 0, hours = 0, minutes = 0, seconds = 0):
    with psycopg2.connect(CONNECTION) as conn:
        date = datetime.datetime.now()
        current_date = f"{date.year}-{date.month}-{date.day} {date.hour}:{date.minute}:{date.second}" 
        target_year = date.year - int(years)
        target_month = date.month - int(months)
        target_day = date.day - int(days)
        target_hour = date.hour - int(hours)
        target_minute = date.minute - int(minutes)
        target_second = date.second - float(seconds)
        while target_second < 0:
            target_second += 60
            target_minute -= 1
        while target_minute < 0:
            target_minute += 60
            target_hour -= 1
        while target_hour < 0:
            target_hour += 24
            target_day -= 1       
        while target_day <= 0:
            target_day += 30
            target_month -= 1
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        if target_month == 2 and target_day > 28:
            target_month = 3
            target_day -= 28
        target_date = f"{target_year}-{target_month}-{target_day} {target_hour}:{target_minute}:{target_second}"  
        query = f"SELECT * FROM {tsdb_table} WHERE p_uid = '{p_uid}'"
        query += f" AND timestamp <= '{current_date}'"
        query += f" AND timestamp >= '{target_date}'"
        cursor = conn.cursor()
        try: 
            cursor.execute(query)
            conn.commit()
            result = cursor.fetchall()
        except psycopg2.errors as e:
            sys.stderr.write(f'error: {e}\n')
        cursor.close()
    
    return result

@router.get("/l_uid/{l_uid}/{func}")
async def get_puid_records(l_uid: str, func: str, fromdate = "", todate = "", p_uid = ""):
    with psycopg2.connect(CONNECTION) as conn:
        query = f"SELECT {func}(value) FROM {tsdb_table} WHERE l_uid = '{l_uid}'"
        if fromdate != "":
            query += f"AND timestamp >= '{fromdate}'"
        if todate != "":
            query += f"AND timestamp <= '{todate}'"
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