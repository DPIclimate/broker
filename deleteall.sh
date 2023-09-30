#!/bin/bash

# Load environment variables
source compose/.env

# Truncate the timeseries table
docker exec prod-timescaledb-1 psql -U $TSDB_USER -d $TSDB_DB -p $TSDB_PORT -c "TRUNCATE TABLE public.timeseries CASCADE;"

echo "All entries from the timeseries table have been deleted."

