FROM timescale/timescaledb-ha:pg15-latest

# Switch to root user for installations
USER root

# Install pgBackRest
RUN apt-get update && \
    apt-get install -y wget gnupg2 pgbackrest && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy the pgbackrest initialization script into the container
COPY pgbr_init.sh /docker-entrypoint-initdb.d/pgbr_init.sh

# Copy the custom configuration file to a temporary location
COPY postgres/postgresql.conf /tmp/postgresql.conf

# Create the script to move the configuration file
RUN echo "cp /tmp/postgresql.conf /home/postgres/pgdata/data/postgresql.conf" > /docker-entrypoint-initdb.d/10-copy-config.sh && \
    chmod +x /docker-entrypoint-initdb.d/10-copy-config.sh

# Switch back to the postgres user
USER postgres

