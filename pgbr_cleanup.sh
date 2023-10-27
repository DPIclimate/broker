#!/bin/bash

echo "WARNING! Before continuing, please read the following:"
echo "This file will wipe all pgBackRest files and create start fresh."
echo "This is best done in the case of corruption, or following a logical restore to reset timeline."
read -p "Do you wish to continue? (yes/no): " response

if [[ "$response" != "yes" ]]; then
    echo "Aborting."
    exit 1
fi

# Configuration
PG_BACKREST_VOLUME="prod_pgbackrest_data"

# Find the container name containing "timescaledb-1"
DB_CONTAINER_NAME=$(docker ps --format '{{.Names}}' | grep "timescaledb-1")

# Find the container name containing "iota_tsdb_decoder-1"
DECODER_CONTAINER_NAME=$(docker ps --format '{{.Names}}' | grep "iota_tsdb_decoder-1")

# Stop the TimescaleDB and decoder containers
echo "Stopping decoder container..."
docker stop "$DECODER_CONTAINER_NAME"
echo "Stopping TimescaleDB container..."
docker stop "$DB_CONTAINER_NAME"

# Clear the data within the volume using a temporary container
echo "Clearing data inside pgbackrest_data volume..."
docker run --rm -v "${PG_BACKREST_VOLUME}:/data" busybox sh -c 'rm -rf /data/*'

sleep 5
# Start the TimescaleDB and Decoder containers
echo "Starting TimescaleDB container..."
docker start "$DB_CONTAINER_NAME"
docker exec -t "$DB_CONTAINER_NAME" pgbackrest --stanza=demo --config=/home/postgres/pgdata/backup/pgbackrest.conf stanza-create
sleep 1
echo "Starting decoder container..."
docker start "$DECODER_CONTAINER_NAME"
echo "Process completed."

