#!/bin/bash

startBroker () {
	# Build docker images
	echo -e "Building Local Docker Images"
	docker build -q -t broker/python-base -f images/restapi/Dockerfile .
	docker build -q -t broker/ttn_decoder -f images/ttn_decoder/Dockerfile .
	docker build -q -t broker/mgmt-app -f src/www/Dockerfile .

	# Apply kubernetes configuration
	# Apply namepsace first so it is available for other resources
	echo -e "Applying Kubernetes Configurations"
	kubectl apply -f kubernetes/namespace.yaml
	kubectl apply -f kubernetes/env-configmap.yaml
	kubectl apply -f kubernetes/services
	kubectl apply -f kubernetes/nodeports.yaml
}

stopBroker () {
	# Delete namespace (and all resources in it)
	echo -e "Removing Kubernetes Configurations"
	kubectl delete namespace/broker
}

listResources () {
	# Get namespace resources
	kubectl get all --namespace=broker
}

# Get the mode to run in
if [ "$1" = "status" ]; then
	echo "Getting all Broker System Resources"
	listResources
elif [ "$1" = "stop" ]; then
	echo "Stopping Broker System"
	stopBroker
elif [ "$1" = "restart" ]; then
	echo "Restarting Broker System"
	stopBroker
	startBroker
else
	echo "Starting Broker System"
	startBroker
	listResources
fi
