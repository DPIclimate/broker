#!/bin/bash

echo 'starting docker container'
docker run -d --rm --name influxdb -p 8086:8086 influxdb:2.7.0 >/dev/null

docker ps | grep -q "influxdb" && echo "influxdb running"