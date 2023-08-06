#!/bin/bash

echo 'starting docker container'
docker run -d --rm --name influxdb -p 8086:8086 \
	-e DOCKER_INFLUXDB_INIT_MODE=setup \
	-e DOCKER_INFLUXDB_INIT_USERNAME=Desmodena \
	-e DOCKER_INFLUXDB_INIT_PASSWORD=password \
	-e DOCKER_INFLUXDB_INIT_ORG=ITC303 \
	-e DOCKER_INFLUXDB_INIT_BUCKET=DPI \
	influxdb:2.7.0 >/dev/null

docker ps | grep -q "influxdb" && echo "influxdb running"
