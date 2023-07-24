#!/bin/bash

# Make all the Python files available to the cluster

PYTHON="src/python/"

# Each folder under src/python to be converted to a ConfigMap file

kubectl create configmap broker-config --from-file=$PYTHON #add broker-cli and BrokerConstants
kubectl create configmap api-client-config --from-file=$PYTHON/api/client
kubectl create configmap delivery-config --from-file=$PYTHON/delivery
kubectl create configmap logical-mapper-config --from-file=$PYTHON/logical_mapper
kubectl create configmap pdmodels-config --from-file=$PYTHON/pdmodels
kubectl create configmap pollers-config --from-file=$PYTHON/pollers
kubectl create configmap restapi-config --from-file=$PYTHON/restapi
kubectl create configmap ttn-config --from-file=$PYTHON/ttn
kubectl create configmap util-config --from-file=$PYTHON/util
kubectl create configmap ydoc-config --from-file=$PYTHON/ydoc

kubectl create configmap rabbitmq-config --from-file=config/rabbitmq

kubectl create configmap db-config --from-file=db/init.d

# ttn-decoder

# website

#minikube mount $parent_dir/broker:/home/broker &
#minikube mount $parent_dir/ttn-formatters:/home/ttn-formatters &
#minikube mount $parent_dir/databolt:/home/databolt &