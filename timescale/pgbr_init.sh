#!/usr/bin/env bash

# Function to wait for PostgreSQL to be ready
wait_for_postgres() {
    until pg_isready -h localhost -U postgres; do
        echo "Waiting for PostgreSQL to start..."
        sleep 2
    done
}

# Wait for PostgreSQL
wait_for_postgres

# Run stanza-create (only if the stanza doesn't already exist)
if ! pgbackrest info --stanza=demo --config=/etc/pgbackrest/pgbackrest.conf 2>&1 | grep -q "stanza: demo"; then
    pgbackrest --stanza=demo --config=/etc/pgbackrest/pgbackrest.conf stanza-create
fi

# Continue with the default TimescaleDB entrypoint (or whatever command you want to run next)
exec "$@"

