#!/bin/bash

echo 'starting docker container'
docker run -d --rm --name timescaledb -p 127.0.0.1:5432:5432 -e POSTGRES_PASSWORD=admin timescale/timescaledb:latest-pg15 >/dev/null

echo '---'

docker ps | grep -q "timescaledb" && echo "timescaledb running"

