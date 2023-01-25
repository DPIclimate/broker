#!/usr/bin/env bash
set -euo pipefail

# Setting +e so the script does not exit while testing for which docker compose command to use.
set +e
docker compose --help &>/dev/null
if [ $? = 0 ]; then
    DC="docker compose"
else
    docker-compose --help &>/dev/null
    if [ $? = 0 ]; then
        DC="docker-compose"
    else
        echo docker compose not found
        exit 1
    fi
fi
set -e

RUN_MODE=$(basename $PWD)
echo $DC

if [ "$RUN_MODE" != test ]; then
    if [ "$RUN_MODE" != production ]; then
        echo "Invalid run mode [$RUN_MODE]"
        exit 1
    else
        RUN_MODE=prod
    fi
fi

echo $RUN_MODE

exec $DC -p $RUN_MODE -f ../docker-compose.yml -f ./$RUN_MODE.yml $*
