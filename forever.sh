#!/bin/bash

while [ 1 ]; do
	if [ -f /tmp/stop.txt ]; then
		exit 0
	fi
	sleep 10
done
