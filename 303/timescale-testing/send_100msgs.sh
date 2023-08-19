#!/usr/bin/env bash

while IFS= read -r line; do
    docker exec test-iota_tsdb_decoder-1 python -c "import timescale.test.DBTests3 as ts; ts.send_rabbitmq_msg('$line')"
done < "../../src/python/timescale/test/msgs/msgs100"