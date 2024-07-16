#!/bin/bash

# Load environment variables from .env file
source compose/.env 2>/dev/null

# Warning prompt about timelines
echo "WARNING! Before continuing, please read the following:"

echo "Postgres makes use of timelines, which keep logs of changes from a point in time, allowing for backups to be restored to a certain point in its history."
echo
echo "Because of this to this, you should only attempt restore to a point prior to your last restore as part of that timeline, otherwise the restore will fail to complete."
echo "For example: If you take two backups, A (the first one) and B (the more recent one), if you restore to A, B will now be incompatible with the current timeline."
echo
echo "If you have recently performed a logical backup restore (ts_restore.sh), the timeline history will be erased,"
echo "resulting in all physical backups prior to restore becoming incompatible with the current database."
echo
read -p "Do you wish to continue? (yes/no): " choice

if [[ "$choice" != "yes" ]]; then
    echo "Exiting restore process."
    exit 1
fi

# Find the container name containing "timescaledb-1"
DB_CONTAINER_NAME=$(docker ps --format '{{.Names}}' | grep "timescaledb-1")
if [ -z "$DB_CONTAINER_NAME" ]; then
    echo "Error: Container containing 'timescaledb-1' not found."
    exit 1
fi

# Find the container name containing "iota_tsdb_decoder-1"
DECODER_CONTAINER_NAME=$(docker ps --format '{{.Names}}' | grep "iota_tsdb_decoder-1")
if [ -z "$DECODER_CONTAINER_NAME" ]; then
    echo "Error: Container containing 'iota_tsdb_decoder-1' not found."
    exit 1
fi

# Check if environment variables are set
if [ -z "$TSDB_USER" ] || [ -z "$TSDB_DB" ] || [ -z "$TSDB_PASSWORD" ]; then
    echo "Error: Required environment variables are not set."
    exit 1
fi

# List the backups without starting the temp container
echo "Available backups:"
docker exec -t $DB_CONTAINER_NAME pgbackrest info --stanza=demo

# Ask the user for the backup label
read -p "Enter the backup label to restore (or press Enter for the latest): " BACKUP_LABEL

# Stop the original container and decoder to stop message consumption
echo "Stopping the original container..."
docker stop $DECODER_CONTAINER_NAME
docker stop $DB_CONTAINER_NAME

# Start a new temporary container using the same image but with a different entry point
TEMP_CONTAINER_NAME="temp_postgres_restore"
echo "Starting a temporary container without PostgreSQL..."
docker run -d \
  --name $TEMP_CONTAINER_NAME \
  -v tsdb_db:/home/postgres/pgdata/data \
  -v prod_pgbackrest_data:/var/lib/pgbackrest \
  -v $(pwd)/timescale/pgbackrest/pgbackrest.conf:/home/postgres/pgdata/backup/pgbackrest.conf \
  custom-timescaledb:latest /bin/sh -c "tail -f /dev/null & wait"

# Ensure the PostgreSQL data directory is empty
echo "Ensuring the PostgreSQL data directory is empty..."
docker exec -t $TEMP_CONTAINER_NAME sh -c "rm -rf /home/postgres/pgdata/data/* && rm -rf /home/postgres/pgdata/data/.*"

# Restore the database on the temporary container
echo "Restoring the database..."
if [ -z "$BACKUP_LABEL" ]; then
    docker exec -t $TEMP_CONTAINER_NAME pgbackrest restore --stanza=demo
else
    docker exec -t $TEMP_CONTAINER_NAME pgbackrest restore --stanza=demo --set=$BACKUP_LABEL
fi

# Stop the temporary container
echo "Stopping the temporary container..."
docker stop $TEMP_CONTAINER_NAME
docker rm $TEMP_CONTAINER_NAME

# Start the original containers
echo "Starting the original containers..."
docker start $DB_CONTAINER_NAME
sleep 5
docker exec -it $DB_CONTAINER_NAME psql -U $TSDB_USER -d $TSDB_DB -c "SELECT pg_wal_replay_resume();"
sleep 1
docker start $DECODER_CONTAINER_NAME

echo "Database restore completed."
