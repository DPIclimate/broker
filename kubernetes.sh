#!/bin/bash

# Get the parent directory of the current directory
parent_dir=$(dirname "$(pwd)")

# Start minikube
minikube start 

# Set minikube docker environment
eval $(minikube -p minikube docker-env)

# Build docker images
docker build -t broker/python-base -f images/restapi/Dockerfile .
docker build -t broker/ttn_decoder -f images/ttn_decoder/Dockerfile .
docker build -t broker/mgmt-app -f src/www/Dockerfile .


# Mount directories
minikube mount $parent_dir/broker:/home/broker &
minikube mount $parent_dir/ttn-formatters:/home/ttn-formatters &
minikube mount $parent_dir/databolt:/home/databolt &

# Apply kubernetes configuration
cd kubernetes
kubectl apply  -f prometheus.yaml 
kubectl apply -f .


# Open minikube dashboard
minikube dashboard
