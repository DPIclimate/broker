#!/bin/bash

# Get the mode to run in
if [ "$1" = "status" ]; then
    echo "Getting all Broker System Resources"

	# Get namespace resources
	kubectl get all --namespace=broker

elif [ "$1" = "stop" ]; then
    echo "Stopping Broker System"

	# Delete namespace (and all resources in it)
	kubectl delete namespace/broker

elif [ "$1" = "restart" ]; then
    echo "Restarting Broker System"

	# Delete namespace (and all resources in it)
	kubectl delete namespace/broker
	
	# Build docker images
	echo -e "Building Local Docker Images"
	docker build -q -t broker/python-base -f images/restapi/Dockerfile .
	docker build -q -t broker/ttn_decoder -f images/ttn_decoder/Dockerfile .
	docker build -q -t broker/mgmt-app -f src/www/Dockerfile .

	# Apply kubernetes configuration
	# Apply namepsace first so it is available for other resources
	kubectl apply -f kubernetes/namespace.yaml
	kubectl apply -f kubernetes/env-configmap.yaml
	kubectl apply -f kubernetes/services
	kubectl apply -f kubernetes/nodeports.yaml

else
	echo "Starting Broker System"

	# Build docker images
	echo -e "Building Local Docker Images"
	docker build -q -t broker/python-base -f images/restapi/Dockerfile .
	docker build -q -t broker/ttn_decoder -f images/ttn_decoder/Dockerfile .
	docker build -q -t broker/mgmt-app -f src/www/Dockerfile .

	# Apply kubernetes configuration
	kubectl apply -f kubernetes/namespace.yaml
	kubectl apply -f kubernetes/env-configmap.yaml
	kubectl apply -f kubernetes/services
	kubectl apply -f kubernetes/nodeports.yaml

fi
