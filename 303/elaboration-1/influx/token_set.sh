#!/bin/bash

set INFLUXDB_TOKEN $(docker exec influxdb influx auth list | grep -A 1 "Desmodena's Token" | awk '$3 ~ /^Token/{getline; print $4}')