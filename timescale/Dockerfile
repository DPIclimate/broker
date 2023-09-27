FROM timescale/timescaledb-ha:pg15-latest

# Install pgBackRest
USER root

# Install pgBackRest from the default Ubuntu repositories
RUN apt-get update \
    && apt-get install -y wget gnupg2 pgbackrest

    
# Copy the pgbackrest initialization script into the container
COPY pgbr_init.sh /usr/local/bin/pgbr_init.sh

# Make the script executable
RUN chmod +x /usr/local/bin/pgbr_init.sh

USER postgres
