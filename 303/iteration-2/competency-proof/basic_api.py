import db
from fastapi import FastAPI

# To run, use the api.sh file to create the endpoints for the API.
# This requires uvicorn to be installed, as it sets up the endpoints.

# Access via CLI using curl:
# e.g. "curl http://localhost:8000/get/" or "curl http://localhost:8000/get/last/60"

# Can also access in a web browser with the same URL.

app = FastAPI()

@app.get("/")
async def read_main():
    return {"msg":"hi there!!"}


@app.get("/get/")
def query_all():
    query = "SELECT * FROM test_db"
    response = db.get_http_query(query).json()

    return response['dataset']

    
@app.get("/get/last/{seconds}")
def query_by_time(seconds: int = 5, host = "localhost"):
    # Convert to microseconds as Questdb uses.
    time = seconds * 1000000

    query = f"SELECT * FROM test_db WHERE timestamp > sysdate() - {time}"
    response = db.get_http_query(query, host).json()

    return response['dataset']
