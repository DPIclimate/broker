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
