#!/bin/bash

echo 'stopping prometheus...'
docker stop prometheus > /dev/null
docker stop json_exporter > /dev/null
kill -9 `ps | grep python3 | grep -Eo "[0-9]{4,5}"`