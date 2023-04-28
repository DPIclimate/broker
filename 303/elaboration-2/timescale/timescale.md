# <u>Timescale Database:</u>

### Purpose of Time-series Databases:

- Provide a better way to work with time-related data, for the purposes
  of aggregating it and working through it quicker than typical
  databases.

- Provide ways to analyse with the time-related data in a fast and easy
  way, also often visually.

- Provide storage efficiency for time-related data.

- Often provide horizontal scalability to account for scenarios with
  large amounts of data.

### Basic Details:

- Uses Apache 2.0 licensing.

- Built on PostgreSQL with additions for time-series data.

- Hyperscale architecture allows for horizontal scalability. (requires
  setup and adds complexity, likely irrelevant for our project)

### Major Features:

- **Hypertables**: PostgreSQL tables that automatically partition your
  data by time. Otherwise are functionally the same, and can exist
  alongside regular tables. Helps with performance over time.

- **Continuous aggregates**: Allows for easy and quick aggregation of
  data to minutes/hours with averages during the range. Has no effect on
  INSERT operation performance. These are setup with a query that is
  precomputed, and uses a process that consistently updates upon the
  relevant tables being updated.

- **Compression**: Significant compression (reduces chunk size by more
  than 90%) can be present in Hypertables to reduce disk space required,
  and can speed up queries.

### Other Notables:

- Support for InfluxDB's Line Protocol and Prometheus's remote_write
  protocol.

- Use of PostgreSQL allows for support of useful Object Relational
  Mapping (ORM) frameworks, like SQLAlchemy, a commonly used Python
  library. Allows for you to work with database tables as python
  classes, and rows within as objects. Could be useful for API
  functionality.

- Can be complex in comparison to alternatives.

- Though good query performance, can be slower than alternatives
  depending on the query type.

### Setup of Database:
<https://docs.timescale.com/self-hosted/latest/install/installation-docker/#set-up-the-timescaledb-extension>

The doc above describes the basic way to run the Docker image on your
system.

Essentially, you make use of a Docker run command to setup a Docker
image, something similar to below:

docker run -d --rm --name timescaledb -p 127.0.0.1:5432:5432 -e
POSTGRES_PASSWORD=admin timescale/timescaledb:latest-pg15 \>/dev/null

This sets up a timescaledb image using postgres15, with basic details in
place. It also won’t store any data after closing due to the use of
“--rm” removing the container. It will also start with a database called
postgres and user called postgres by default.

From here you can access it either via psql, a CLI for use with
PostgreSQL, or an alternative option.

In the case of my test setup, simply run the start.sh and stop.sh to
both start and stop the test database. This is setup to discard its data
when stopped, and running timescale.py will populate it with the sample
data, and retrieve the data at the end, both using JSON format.

### Use with Python:
<https://docs.timescale.com/quick-start/latest/python/>

Install and import psycogpg2, a library used for PostgreSQL to execute
raw SQL queries and is secure from SQL injection.

From here you must define a connection string like the below:

CONNECTION = f"postgres://{username}:{password}@{host}:{port}/{dbname}"

Then you can define a psycopg2 connection using it’s connect method, and
also defining a cursor to allow for querying.

conn = psycopg2.connect(CONNECTION)  
cursor = conn.cursor()

From here you write out statements as strings, and use them with the
execute method, prior to running the commit method to send all
statements to the DB.

cursor.execute("SELECT create_hypertable('test_table', 'timestamp');")  
conn.commit()

This is only the most basic example, the code can become much more
complex depending on how modular you design your methods to be.
