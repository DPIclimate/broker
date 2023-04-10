#!/bin/bash

echo 'stopping rabbitmq...'
docker stop rabbitmq >/dev/null
echo 'stopping questdb...'
docker stop questdb >/dev/null
echo 'stopping api...'
docker stop api >/dev/null
