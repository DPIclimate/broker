#!/bin/bash

docker run -d --rm --name questdb -p 9000:9000 -p 9009:9009 -p 8812:8812 -p 9003:9003 questdb/questdb:7.0.1 >/dev/null

docker ps | grep -q "questdb" && echo "questdb running"
