#!/usr/bin/env bash
set -euo pipefail

BROKER_ROOT=$(cd $(dirname $0); pwd)
MODE=${1:-test}

if [ ! -f $BROKER_ROOT/compose/.env ]; then
    echo The file $BROKER_ROOT/compose/.env is missing. Copy $BROKER_ROOT/config/broker.env.template to $BROKER_ROOT/compose/.env and set the values.
    exit 1
fi

cd $BROKER_ROOT
cd compose/$MODE
./dc.sh down
cd $BROKER_ROOT
docker build -q -t broker/python-base -f images/restapi/Dockerfile .
docker build -q -t broker/mgmt-app -f src/www/Dockerfile .

docker_arch=$(docker info --format '{{.Architecture}}')

case "$docker_arch" in
    amd64|x86_64)
        ;;
    arm64|aarch64)
        docker build -q -t postgis/postgis:14-3.5 -f images/postgis_14-3.5/Dockerfile images/postgis_14-3.5
        ;;
    *)
        echo "Unsupported Docker architecture: $docker_arch" >&2
        exit 1
        ;;
esac

cd compose/$MODE
./dc.sh up -d
./dc.sh logs -f
