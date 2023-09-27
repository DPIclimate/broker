#!/bin/bash

# Load environment variables from .env file
source compose/.env

# Configuration
DB_CONTAINER_NAME="prod-timescaledb-1"  # Update with your DB container name if needed
DB_NAME="${TSDB_DB}"
DB_USER="${TSDB_USER}"
DB_PASSWORD="${TSDB_PASSWORD}"

# Check if environment variables are set
if [ -z "$TSDB_USER" ] || [ -z "$TSDB_DB" ] || [ -z "$TSDB_PASSWORD" ]; then
    echo "Error: Required environment variables are not set."
    exit 1
fi

# Execute SELECT query
docker exec -t $DB_CONTAINER_NAME psql -U $DB_USER -d $DB_NAME -P pager=off -c "SELECT * FROM timeseries;"

