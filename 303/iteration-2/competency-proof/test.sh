#!/bin/bash

#at the very least dbhost is required to run
#as api container calls it and requires the ip,
#the rest can just use localhost

container_names=("questdb" "api" "rabbitmq")

for container_name in "${container_names[@]}"; do
	if [ "$(docker inspect -f '{{.State.Running}}' $container_name)" != "true" ]; then
		echo "Error: $container_name is not running"
		exit
	fi
done

db=$(docker inspect questdb | grep -m 1 -oP '(?<=IPAddress": ")[^"]*')
ap=$(docker inspect api | grep -m 1 -oP '(?<=IPAddress": ")[^"]*')
mq=$(docker inspect rabbitmq | grep -m 1 -oP '(?<=IPAddress": ")[^"]*')

python -m pytest -v --dbhost ${db} --aphost ${ap} --mqhost ${mq}
