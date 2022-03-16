#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd $(dirname $0); pwd)
cd $SCRIPT_DIR
exec docker-compose -p prod -f ../docker-compose.yml -f ./prod.yml $*