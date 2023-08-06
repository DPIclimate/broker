#!/usr/bin/env bash

docker exec test-mq-1 rabbitmqadmin publish -u broker -p CHANGEME exchange="amq.default" routing_key="ltsreader_logical_msg_queue" properties="{\"device\":1}" payload="$(cat JSON_message)" 
