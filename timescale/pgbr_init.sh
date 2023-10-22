#!/bin/bash

# Function to wait for PostgreSQL to be ready
wait_for_postgres() {
    until pg_isready -U postgres; do
        echo "Waiting for PostgreSQL to start..."
        sleep 2
    done
}

# Wait for PostgreSQL
wait_for_postgres


if [ ! -f "/var/lib/pgbackrest/backup/demo/backup.info" ]; then
    pgbackrest --stanza=demo --config=/home/postgres/pgdata/backup/pgbackrest.conf stanza-create
fi



# Continue with the default TimescaleDB entrypoint
#exec /usr/local/bin/docker-entrypoint.sh postgres

