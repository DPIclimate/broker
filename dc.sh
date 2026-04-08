#!/usr/bin/env bash
set -euxo pipefail

OVERRIDE_YML=$(basename $PWD).yml

if [ ! -f "$OVERRIDE_YML" ]; then
    echo "File not found: ${$OVERRIDE_YML}"
    exit 1
fi

exec docker compose --profile wombat --profile ttn -f ../docker-compose.yml -f ./$OVERRIDE_YML $*
