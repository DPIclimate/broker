# This image is used for all Python containers in the broker.

FROM python:3
#FROM python:3-alpine3.10

# For debian-based images
RUN groupadd broker && useradd -m -g broker broker

# For alpine-based images
#RUN addgroup -S broker && adduser -S broker -G broker

USER broker
ENV PATH=/home/broker/.local/bin:${PATH}

# Two quiets here to suppress 'old version of pip' warning, given that is what is being upgraded.
RUN pip install --quiet --quiet --user --progress-bar off --upgrade pip

# psycopg2-binary - PostgreSQL driver
# fastapi[all] - everything required to run a FastAPI app
# python-dateutil - improved ISO-8601 timestamp parsing
# pika - RabbitMQ client
RUN pip install --quiet --user --progress-bar off --upgrade psycopg2-binary fastapi[all] python-dateutil pika

# Work-around for M1 debian-based image, probably only works on (and required by) M1-based macos.
# Fix a broken ARM psycopg2-binary installation by copying a later libpq from the system.
#WORKDIR /home/broker/.local/lib/python3.10/site-packages/psycopg2_binary.libs/
#RUN cp libpq-d97d8807.so.5.9 libpq-d97d8807.so.5.9.org
#RUN cp /usr/lib/aarch64-linux-gnu/libpq.so.5.13 libpq-d97d8807.so.5.9

WORKDIR /home/broker/python/restapi

ENTRYPOINT [ "/bin/bash" ]
