#!/usr/bin/env bash

docker exec test-zak-python-1 python -c "import timescale.Timescale as ts; ts.remove_data_with_value()"
