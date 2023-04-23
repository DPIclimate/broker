#!/bin/bash

echo 'starting docker container'
docker run -d --rm --name prometheus -p 9090:9090 prom/prometheus > dev/null

echo '---'

docker ps | grep -q 'prometheus' && echo 'prometheus running'
