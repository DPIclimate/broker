#!/usr/bin/env bash
set -euo pipefail

# Setting +e so the script does not exit while testing for which docker compose command to use.
set +e
which docker-compose &>/dev/null
if [ $? = 0 ]; then
    DC="docker-compose"
else
    DC="docker compose"
fi
set -e

RUN_MODE=$(basename $PWD)

if [ "$RUN_MODE" != test ]; then
    if [ "$RUN_MODE" != production ]; then
        echo "Invalid run mode [$RUN_MODE]"
        exit 1
    else
        RUN_MODE=prod
    fi
fi

exec $DC -p $RUN_MODE -f ../docker-compose.yml -f ./$RUN_MODE.yml $*
