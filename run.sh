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
echo Building REST API image
docker build -q -t broker/python-base -f images/restapi/Dockerfile .
echo Building TTN decoder image
docker build -q -t broker/ttn_decoder -f images/ttn_decoder/Dockerfile .
echo Building web app image
docker build -q -t broker/mgmt-app -f src/www/Dockerfile .
echo Building QGIS server image
cd images/qgis-server
docker build -q -f Dockerfile -t qgis-server:3.38.1 ./
cd ../../compose/$MODE
./dc.sh up -d
./dc.sh logs -f
