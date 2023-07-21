#!/usr/bin/env bash

docker exec test-zak-python-1 pytest -v timescale/test/IntTest.py
