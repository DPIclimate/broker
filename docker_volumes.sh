#!/usr/bin/env bash

echo "removing production containers"
docker volume remove mq_data
docker volume remove tsdb_db
docker volume remove broker_db

echo "creating volume dockers"
docker volume create mq_data
docker volume create tsdb_db
docker volume create broker_db
