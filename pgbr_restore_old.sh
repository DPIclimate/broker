#!/bin/bash

# Load environment variables from .env file
source compose/.env 2>/dev/null

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

# Stop the original container
echo "Stopping the original container..."
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

# List the backups and capture the output
BACKUP_INFO=$(docker exec -t $TEMP_CONTAINER_NAME pgbackrest info --stanza=demo)

echo "Available backups:"
echo "$BACKUP_INFO"

# Ask the user for the backup label
read -p "Enter the backup label to restore (or press Enter for the latest): " BACKUP_LABEL

# If the user didn't specify a backup label, extract the end time of the latest backup
if [ -z "$BACKUP_LABEL" ]; then
    RECOVERY_TIME=$(echo "$BACKUP_INFO" | grep 'timestamp start/stop:' | tail -n 1 | awk -F' / ' '{print $2}')
else
    # If the user specified a backup label, extract the end time of that backup
    RECOVERY_TIME=$(echo "$BACKUP_INFO" | awk -v label="$BACKUP_LABEL" 'BEGIN {RS=""; FS="\n"} $0 ~ label {for (i=1; i<=NF; i++) if ($i ~ "timestamp start/stop:") {print $i; exit}}' | awk -F' / ' '{print $2}')
fi

# Convert the timestamp to seconds since the Unix epoch, add 2 seconds, and convert it back to the desired format
RECOVERY_TIME=$(date -d "$(echo $RECOVERY_TIME) + 2 seconds" +"%Y-%m-%d %H:%M:%S%z")


# Ensure the PostgreSQL data directory is empty
echo "Ensuring the PostgreSQL data directory is empty..."
docker exec -t $TEMP_CONTAINER_NAME sh -c "rm -rf /home/postgres/pgdata/data/* && rm -rf /home/postgres/pgdata/data/.*"

# Restore the database on the temporary container
echo "Restoring the database..."
if [ -z "$BACKUP_LABEL" ]; then
    docker exec -t $TEMP_CONTAINER_NAME pgbackrest restore --stanza=demo --type=time --target="$RECOVERY_TIME"
else
    docker exec -t $TEMP_CONTAINER_NAME pgbackrest restore --stanza=demo --set=$BACKUP_LABEL --type=time --target="$RECOVERY_TIME"
fi

# After the restoration process
if [ ! -z "$BACKUP_LABEL" ]; then
    # Get a list of all backups
    ALL_BACKUPS=$(docker exec -t $TEMP_CONTAINER_NAME pgbackrest info --stanza=demo | grep backup: | awk '{print $2}')

    # Flag to start deleting backups
    DELETE_FLAG=0

    # Loop through each backup
    for BACKUP in $ALL_BACKUPS; do
        # If we've reached the backup we restored from, start the deletion process for subsequent backups
        if [ "$BACKUP" == "$BACKUP_LABEL" ]; then
            DELETE_FLAG=1
            continue
        fi

        # If the flag is set, delete the backup
        if [ $DELETE_FLAG -eq 1 ]; then
            echo "Deleting backup $BACKUP..."
            docker exec -t $TEMP_CONTAINER_NAME pgbackrest --stanza=demo delete --set=$BACKUP
        fi
    done
fi

# Stop the temporary container
echo "Stopping the temporary container..."
docker stop $TEMP_CONTAINER_NAME
docker rm $TEMP_CONTAINER_NAME

# Start the original container normally
echo "Starting the original container normally..."
docker start $DB_CONTAINER_NAME

echo "Database restored successfully."

sleep 10
echo "Promoting the database to accept connections..."
docker exec -it $DB_CONTAINER_NAME psql -U $TSDB_USER -d $TSDB_DB -c "SELECT pg_wal_replay_resume();"


