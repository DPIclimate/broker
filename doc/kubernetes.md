# Kubernetes

## Introduction

There are provisions here to run the broker service using Kubernetes for orchestration rather than Docker Compose. This will allow for future expansion of the system to greater scales.  
The current implementation simply runs all microservices with a single replica set, host path volumes, and NodePort networking. This is the best method for a drop in replacement to Docker Compose and assumes Kubernetes is running as a Single Node Cluster.

## Requirements

- Docker (to build local images)
- docker-cri
- Kubernetes (Running as a single node cluster)
  - Kubeadm
  - Kubectl
  - Kubelet

## Local Container Images

Currently there are three local container images built for the broker system:

- `broker/python-base`
- `broker/mgmt-app`
- `broker/ttn_decoder`

So long as your kubernetes cluster is using the [docker-cri](https://kubernetes.io/docs/setup/production-environment/container-runtimes/#docker) driver it should be able to read these locally built images.  
In future the broker should use hosted images, either using an online repository such as docker hub or an internally hosted repository. As each node (Server) in the cluster will need to access the same images, these should not be locally built as that can introduce varience.

## Volume Storage

There are several reasons that the container images require access to local node storage. Below are the listed reasons and how they are currently implemented.  
Mostly this uses [HostPath](https://kubernetes.io/docs/concepts/storage/volumes/#hostpath) which is unideal as it only really works in a single node cluster enviroment.

### Python Source Files

Each of the Python container images require access to the python source files in order to run its service. Currently this is implemented using `HostPath` and assumes the source files are located at `/opt/broker/src/python`.  
In future it would be better to copy the source files to the container images when they are built. Note, however, that this would prevent modifying source code without rebuilding the images.

### Configuration Files

The `db` and `mq` services both require configuration files to be included for proper operation. Currently this is implemented using `HostPath` in order to maintain compatibility with Docker Compose.  
These files are assumed to be at `/opt/broker/db/init.d/init.db.sql` and `/opt/brokerconfig/rabbitmq/enabled_plugins` for each respective service.  
In future this should be implemented with a [ConfigMap](https://kubernetes.io/docs/concepts/storage/volumes/#configmap).

### TTN Formatters

The `ttn-decoder` service requires access to the files found in [ttn-formatters](https://github.com/DPIclimate/ttn-formatters). Currently this is implemented using `HostPath`.
These files are assumed to be located at `/opt/ttn-formatters`.  
In future these files should be built into the `ttn-decoder` image.

### Persistant Data

The `db` and `mq` services both require storage volumes in order to keep data persistant between reboots and migrations. Currently this is implemented using `HostPath`.  
Data is assumed to be written to `/opt/broker_data/db` and `/opt/broker_data/mq` for each service respectively.  
In future this should use some other [volume](https://kubernetes.io/docs/concepts/storage/volumes/#volume-types) type but that will depend on where the cluster is deployed.

### Data Output

The `frred` delivery service needs to write data to a databolt directory. Currently this is implemented using `HostPath`.  
Data is assumed to be written to the `/opt/databolt/raw_data` directory.
In future this should use some other volume type that databolt will also be able to read from.

## Networking

Internally each container in the cluster is able to access other containers using dns pointing to `services`. Each microservice that hosts a network port has a service definition in its configuration yaml. A service essentially proxies requests from its own port to any matching pods (in our case each services matches one pod and each pod contains one container).

Ports which need to be exposed outside the cluster are exposed using [NodePort](https://kubernetes.io/docs/concepts/services-networking/service/#type-nodeport) This will proxy requests from ports on the node itself to the service.  
By default the ports that are registered as node ports for each service is random in the range `30000-32767`. This range can be changed when setting up your cluster and you can manually choose a port within this range by specifying the `nodePort` property in the service definition.  
You will need to either proxy or port forward requests to the node in order to use 'standard' port numbers.  
Check which node ports have been allocated with the `kubectl get svc` command.

In future, externally accesible ports should use an external [Load Balancer](https://kubernetes.io/docs/concepts/services-networking/service/#loadbalancer)

## Running

Each microservice from the `docker-compose.yml` has been converted to its own Kubernetes YAML file.  
This currently translates to 13 YAML files available under the `broker/kubernetes` folder.

Simply ensure the docker images have been built locally and apply these configuration files to your Kubernetes node to get the system running.  
Run the following commands to do this manually  
`kubectl apply -f kubernetes/namespace.yaml` Creates the namespace resources will be allocated to  
`kubectl apply -f kubernetes/env-configmap.yaml` Sets up the configmap that stores our environment variables  
`kubectl apply -f kubernetes/services` Creates all the microservice deployments

To stop and remove all resource configurations we just need to delete the namespace.  
`kubectl delete all --all --namespace=broker`

### Script

There is a script created `./kubernetes.sh` which will do this automatically for you.  
The script can also take an additional parameter to configure which mode it runs in.

- `./kubernetes.sh start` - (default) Builds the docker images and applies the configuration files to the Kubernetes cluster under the `broker` namespace.
- `./kubernetes.sh stop` - Stop all running services and remove the configuration from the Kubernetes cluster.
- `./kubernetes.sh restart` - Just runs `stop` and then `start`. Note: This will cycle any dynamic IPs or NodePorts.
