# This file originally from https://github.com/pikhovkin/postgresql-postgis-timescaledb
# Updated to use later versions of Alpine, Postgis, and TimescaleDB.

FROM postgres:18.1-alpine3.23

ENV ALPINE_VERSION=v3.23
ENV LANG=en_AU.UTF-8
ENV LC_ALL=en_AU.UTF-8
ENV POSTGRES_INITDB_ARGS="--locale=en_AU.UTF-8 --encoding=UTF8"

# https://postgis.net/docs/manual-3.5/postgis_installation.html
ENV POSTGIS_VERSION=3.6.1
RUN set -ex \
    \
    && apk add --no-cache --virtual .fetch-deps \
        --repository http://dl-cdn.alpinelinux.org/alpine/$ALPINE_VERSION/main \
        --repository http://dl-cdn.alpinelinux.org/alpine/$ALPINE_VERSION/community \
        build-base \
        ca-certificates \
        openssl \
        git \
        tar \
    && apk add --no-cache --virtual .build-deps \
        --repository http://dl-cdn.alpinelinux.org/alpine/$ALPINE_VERSION/main \
        --repository http://dl-cdn.alpinelinux.org/alpine/$ALPINE_VERSION/community \
        make \
        automake \
        autoconf \
        libtool \
        file \
        gcc \
        g++ \
        perl \
        clang19 \
        clang19-dev \
        llvm19 \
        llvm19-dev \
        libxml2-dev \
        \
        json-c-dev \
        geos-dev \
        gdal-dev \
        proj-dev \
        protobuf-c-dev \
        postgresql-dev \
    && apk add --no-cache --virtual .postgis-rundeps \
        --repository http://dl-cdn.alpinelinux.org/alpine/$ALPINE_VERSION/main \
        --repository http://dl-cdn.alpinelinux.org/alpine/$ALPINE_VERSION/community \
        json-c \
        geos \
        gdal \
        proj \
        protobuf-c \
    \
    && wget -O postgis.tar.gz "https://github.com/postgis/postgis/archive/$POSTGIS_VERSION.tar.gz" \
    && mkdir -p /usr/src/postgis \
    && tar --extract --file postgis.tar.gz --directory /usr/src/postgis --strip-components 1 \
    && rm postgis.tar.gz \
    \
    && cd /usr/src/postgis \
    && ./autogen.sh \
    && ./configure \
    && make -s \
    && make -s install \
    && cd / \
    && rm -rf /usr/src/postgis \
    && apk del .fetch-deps .build-deps

# https://docs.timescale.com/self-hosted/latest/install/installation-source/
ENV TIMESCALEDB_VERSION=2.25.0
RUN set -ex \
    && apk add --no-cache --virtual .fetch-deps \
        --repository http://dl-cdn.alpinelinux.org/alpine/$ALPINE_VERSION/main \
        --repository http://dl-cdn.alpinelinux.org/alpine/$ALPINE_VERSION/community \
        build-base \
        ca-certificates \
        git \
        tar \
    && apk add --no-cache --virtual .build-deps \
        --repository http://dl-cdn.alpinelinux.org/alpine/$ALPINE_VERSION/main \
        --repository http://dl-cdn.alpinelinux.org/alpine/$ALPINE_VERSION/community \
        make \
        cmake \
        gcc \
        clang \
        clang-dev \
        llvm-dev \
        dpkg \
        dpkg-dev \
        util-linux-dev \
        libc-dev \
        coreutils \
        krb5-dev \
    && apk add --no-cache --virtual .timescaledb-rundeps \
        --repository http://dl-cdn.alpinelinux.org/alpine/$ALPINE_VERSION/main \
        --repository http://dl-cdn.alpinelinux.org/alpine/$ALPINE_VERSION/community \
        openssl \
        openssl-dev \
    \
    && wget -O timescaledb.tar.gz "https://github.com/timescale/timescaledb/archive/$TIMESCALEDB_VERSION.tar.gz" \
    && mkdir -p /usr/src/timescaledb \
    && tar --extract --file timescaledb.tar.gz --directory /usr/src/timescaledb --strip-components 1 \
    && rm timescaledb.tar.gz \
    \
    && cd /usr/src/timescaledb \
    && ./bootstrap -DPROJECT_INSTALL_METHOD="docker" -DREGRESS_CHECKS=OFF \
    && cd ./build && make install \
    \
    && cd / \
    && rm -rf /usr/src/timescaledb \
    && apk del .fetch-deps .build-deps \
    && sed -r -i "s/[#]*\s*(shared_preload_libraries)\s*=\s*'(.*)'/\1 = 'timescaledb,\2'/;s/,'/'/" /usr/local/share/postgresql/postgresql.conf.sample

RUN set -ex \
    && apk add --no-cache --virtual .fetch-deps \
        --repository http://dl-cdn.alpinelinux.org/alpine/$ALPINE_VERSION/main \
        --repository http://dl-cdn.alpinelinux.org/alpine/$ALPINE_VERSION/community \
        musl-locales

COPY exts.sql /docker-entrypoint-initdb.d/
