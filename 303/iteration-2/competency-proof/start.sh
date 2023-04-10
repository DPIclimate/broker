#!/bin/bash
docker stop api >/dev/null
docker rm api >/dev/null
docker build -q -t api .
echo 'starting docker containers'
docker run -d --rm --name questdb -p 9000:9000 -p 9009:9009 -p 8812:8812 -p 9003:9003 questdb/questdb:7.0.1 >/dev/null
docker run -d -it --rm --name rabbitmq --hostname localhost --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3.11-management >/dev/null
docker run -d -it --rm --name api -p 8000:8000 api >/dev/null
echo '---'
docker ps | grep -q "questdb" && echo "questdb running"
docker ps | grep -q "rabbitmq" && echo "rabbitmq running"
docker ps | grep -q "api" && echo "api running"
