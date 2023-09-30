#!/bin/bash
set -e

# Wait for PostgreSQL to start
until pg_isready -U postgres; do
  echo "Waiting for PostgreSQL to start..."
  sleep 1
done

# Set archive mode and restart PostgreSQL
psql -U postgres -c "ALTER SYSTEM SET archive_mode TO 'on';"
pg_ctl restart

