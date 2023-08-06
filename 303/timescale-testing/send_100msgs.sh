#!/usr/bin/env bash

docker exec test-iota_tsdb_decoder-1 python -c "import timescale.test.DBTests3 as ts; ts.TestSingleInsertSpeed('timescale/test/msgs/msgs100', 480)"

