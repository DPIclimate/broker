#!/bin/bash

source compose/.env 2>/dev/null

# Configuration
DB_NAME="${TSDB_DB}"
DB_USER="${TSDB_USER}"
DB_PASSWORD="${TSDB_PASSWORD}"
BACKUP_DIR="backup/"
BACKUP_FILENAME="backup_$(date +'%Y%m%d_%H%M%S').sql"

if [ -z "$TSDB_USER" ] || [ -z "$TSDB_DB" ] || [ -z "$TSDB_PASSWORD" ]; then
    echo "Error: Required environment variables are not set."
    exit 1
fi

# Find the container name containing "timescale-1"
DB_CONTAINER_NAME=$(docker ps --format '{{.Names}}' | grep "timescaledb-1")

if [ -z "$DB_CONTAINER_NAME" ]; then
    echo "Error: Container containing 'timescale-1' not found."
    exit 1
fi

# Check if backup directory exists, if not, create it (for error prevention)
[ -d "$BACKUP_DIR" ] || mkdir -p "$BACKUP_DIR"

# Perform the backup
docker exec -t "$DB_CONTAINER_NAME" pg_dump -U "$DB_USER" -d "$DB_NAME" -F c -b -v -f "/tmp/$BACKUP_FILENAME"

# Copy the backup from the container to the host
docker cp "$DB_CONTAINER_NAME:/tmp/$BACKUP_FILENAME" "$BACKUP_DIR/$BACKUP_FILENAME"

# Remove the backup file from the container
docker exec -t "$DB_CONTAINER_NAME" rm "/tmp/$BACKUP_FILENAME"

echo "Backup completed: $BACKUP_DIR/$BACKUP_FILENAME"

