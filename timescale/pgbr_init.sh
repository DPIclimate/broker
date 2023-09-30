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

# Run stanza-create (only if the stanza doesn't already exist)
#if ! pgbackrest info --stanza=demo --config=/home/postgres/pgdata/backup/pgbackrest.conf 2>&1 | grep -q "stanza: demo"; then
#    pgbackrest --stanza=demo --config=/home/postgres/pgdata/backup/pgbackrest.conf stanza-create >> /var/log/timescale/pgbr_init.log 2>&1
#fi

# Continue with the default TimescaleDB entrypoint
#exec /usr/local/bin/docker-entrypoint.sh

