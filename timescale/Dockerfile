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
RUN chmod +x /docker-entrypoint-initdb.d/pgbr_init.sh


# Append custom configurations to the existing postgresql.conf
COPY postgres/custom_postgresql.conf /tmp/custom_postgresql.conf
RUN echo "cat /tmp/custom_postgresql.conf >> /home/postgres/pgdata/data/postgresql.conf" > /docker-entrypoint-initdb.d/10-append-config.sh


# Switch back to the postgres user
USER postgres

