#!/bin/bash

echo 'starting docker container'
python3 -m http.server 8080 &
docker run -d --rm --name json_exporter -p 7979:7979 -v $PWD/config/config.yml:/config.yml quay.io/prometheuscommunity/json-exporter --config.file=/config.yml 
docker run -d --rm --name prometheus -p 9090:9090 -v $PWD/config/prometheus.yml:/etc/prometheus/prometheus.yml prom/prometheus 

echo '---'

docker ps | grep -q "prom/prometheus" && echo 'prometheus running'
docker ps | grep -q "json_exporter" && echo 'json_exporter running'
docker ps