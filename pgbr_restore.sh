#!/bin/bash

# Load environment variables from .env file
source compose/.env

# Configuration
BACKUP_REPO_PATH="/var/lib/pgbackrest"
BACKUP_REPO_HOST_PATH="./pgbackrest_repo"

# Find the container name containing "timescale-1"
DB_CONTAINER_NAME=$(docker ps --format '{{.Names}}' | grep "timescaledb-1")

if [ -z "$DB_CONTAINER_NAME" ]; then
    echo "Error: Container containing 'timescale-1' not found."
    exit 1
fi

# Check if environment variables are set
if [ -z "$TSDB_USER" ] || [ -z "$TSDB_DB" ] || [ -z "$TSDB_PASSWORD" ]; then
    echo "Error: Required environment variables are not set."
    exit 1
fi

# Restore the database
docker exec -t $DB_CONTAINER_NAME pgbackrest restore

echo "Database restored successfully."

