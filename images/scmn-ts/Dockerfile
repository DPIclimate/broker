# This Dockerfile creates an image with the same verions of Postgresql & TimescaleDB as on the SCMN
# production VM.
FROM postgres:14-bookworm

RUN apt-get update && apt-get install -yq \
    build-essential \
    cmake \
    git \
    postgresql-server-dev-14 \
    libssl-dev \
    libkrb5-dev \
    postgresql-14-postgis-3 \
    postgresql-14-postgis-3-scripts \
    wget \
    && rm -rf /var/lib/apt/lists/*

RUN wget https://github.com/timescale/timescaledb/archive/refs/tags/2.9.2.tar.gz \
    && tar xvzf 2.9.2.tar.gz \
    && cd timescaledb-2.9.2 \
    && ./bootstrap \
    && cd build && make && make install \
    && cd ../.. \
    && rm -rf timescaledb-2.9.2 2.9.2.tar.gz

# Configure PostgreSQL to load TimescaleDB
RUN echo "shared_preload_libraries = 'timescaledb'" >> /usr/share/postgresql/postgresql.conf.sample

# This init script will be replaced by scripts mounted into the container at run time,
# but having this as a fall-back means the image may be useful for other purposes.
RUN mkdir -p /docker-entrypoint-initdb.d
RUN echo "#!/bin/bash\n\
set -e\n\
\n\
psql -v ON_ERROR_STOP=1 --username \"\$POSTGRES_USER\" --dbname \"\$POSTGRES_DB\" <<-EOSQL\n\
    CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;\n\
    CREATE EXTENSION IF NOT EXISTS postgis CASCADE;\n\
EOSQL" > /docker-entrypoint-initdb.d/init-extensions.sh

RUN chmod +x /docker-entrypoint-initdb.d/init-extensions.sh

EXPOSE 5432

CMD ["postgres"]
