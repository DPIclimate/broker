#!/usr/bin/env bash
set -euo pipefail

RUN_MODE=$(basename $PWD)

if [ "$RUN_MODE" != test ]; then
    if [ "$RUN_MODE" != production ]; then
        echo "Invalid run mode [$RUN_MODE]"
        exit 1
    else
        RUN_MODE=prod
    fi
fi

exec docker compose --profile ttn --profile ydoc --profile wombat --profile ubidots --profile pollers --profile frred -p $RUN_MODE -f ../docker-compose.yml -f ./$RUN_MODE.yml $*
