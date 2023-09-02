#!/bin/bash

# Load environment variables from .env file
source compose/.env

# Configuration
COMPOSE_PROJECT_DIR="compose/"  # Update this path if needed
DB_NAME="${TSDB_DB}"
DB_USER="${TSDB_USER}"
DB_PASSWORD="${TSDB_PASSWORD}"
BACKUP_DIR="backup/"  # Update this path if needed

# Check if environment variables are set
if [ -z "$TSDB_USER" ] || [ -z "$TSDB_DB" ] || [ -z "$TSDB_PASSWORD" ]; then
    echo "Error: Required environment variables are not set."
    exit 1
fi

# Check if backup filename is provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <backup_filename>"
    exit 1
fi

BACKUP_FILENAME="$1"

# Check if file exists
if [ ! -f "$BACKUP_DIR/$BACKUP_FILENAME" ]; then
    echo "Error: File $BACKUP_DIR/$BACKUP_FILENAME does not exist."
    exit 1
fi

# Find the container name containing "timescaledb-1"
DB_CONTAINER_NAME=$(docker ps --format '{{.Names}}' | grep "timescaledb-1")

if [ -z "$DB_CONTAINER_NAME" ]; then
    echo "Error: Container containing 'timescaledb-1' not found."
    exit 1
fi

# Copy the backup from the host to the container
docker cp "$BACKUP_DIR/$BACKUP_FILENAME" "$DB_CONTAINER_NAME:/tmp/$BACKUP_FILENAME"

# Restore
docker exec -t "$DB_CONTAINER_NAME" dropdb -U "$DB_USER" "$DB_NAME"
docker exec -t "$DB_CONTAINER_NAME" createdb -U "$DB_USER" "$DB_NAME"
docker exec -t "$DB_CONTAINER_NAME" pg_restore -U "$DB_USER" -d "$DB_NAME" -v -1 "/tmp/$BACKUP_FILENAME"

# Remove the backup file from the container
docker exec -t "$DB_CONTAINER_NAME" rm "/tmp/$BACKUP_FILENAME"

echo "Restore completed from: $BACKUP_DIR/$BACKUP_FILENAME"

