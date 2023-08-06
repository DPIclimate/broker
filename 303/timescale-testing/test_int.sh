#!/usr/bin/env bash

docker exec test-iota_tsdb_decoder-1 pytest -v timescale/test/IntTest.py
