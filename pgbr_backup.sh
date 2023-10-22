#!/bin/bash

# Load environment variables
source compose/.env 2>/dev/null

# Find the container name containing "timescale-1"
DB_CONTAINER_NAME=$(docker ps --format '{{.Names}}' | grep "timescaledb-1")

if [ -z "$DB_CONTAINER_NAME" ]; then
    echo "Error: Container containing 'timescale-1' not found."
    exit 1
fi

# Determine backup type from the command line argument
BACKUP_TYPE=$1

if [[ "$BACKUP_TYPE" != "full" && "$BACKUP_TYPE" != "diff" && "$BACKUP_TYPE" != "incr" ]]; then
    echo "Error: Invalid backup type. Please specify 'full', 'diff', or 'incr'."
    exit 1
fi

# Perform the backup
docker exec -t $DB_CONTAINER_NAME pgbackrest --config=/home/postgres/pgdata/backup/pgbackrest.conf --stanza=demo --type=$BACKUP_TYPE backup


echo "Backup of type $BACKUP_TYPE completed."

