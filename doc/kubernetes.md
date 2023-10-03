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

### Quick Installation Overview

Below is a brief overview of how to set up a single node Kubernetes cluster using docker-cri on Ubuntu.  
You will need to modify the below steps for your own enviroment.

1. Install Prerequisites

    ```bash
    sudo apt-get update
    sudo apt-get install -y apt-transport-https ca-certificates curl vim git curl wget gnupg
    ```

2. Install Docker

    ```bash
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
    "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update

    sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    ```

3. Install docker-cri

    ```bash
    wget https://github.com/Mirantis/cri-dockerd/releases/download/v0.3.4/cri-dockerd-0.3.4.amd64.tgz
    tar -xvf cri-dockerd-0.3.4.amd64.tgz
    cd cri-dockerd/
    mkdir -p /usr/local/bin
    install -o root -g root -m 0755 ./cri-dockerd /usr/local/bin/cri-dockerd

    sudo tee /etc/systemd/system/cri-docker.service << EOF
    [Unit]
    Description=CRI Interface for Docker Application Container Engine
    Documentation=https://docs.mirantis.com
    After=network-online.target firewalld.service docker.service
    Wants=network-online.target
    Requires=cri-docker.socket
    [Service]
    Type=notify
    ExecStart=/usr/local/bin/cri-dockerd --container-runtime-endpoint fd:// --network-plugin=
    ExecReload=/bin/kill -s HUP $MAINPID
    TimeoutSec=0
    RestartSec=2
    Restart=always
    StartLimitBurst=3
    StartLimitInterval=60s
    LimitNOFILE=infinity
    LimitNPROC=infinity
    LimitCORE=infinity
    TasksMax=infinity
    Delegate=yes
    KillMode=process
    [Install]
    WantedBy=multi-user.target
    EOF

    sudo tee /etc/systemd/system/cri-docker.socket << EOF
    [Unit]
    Description=CRI Docker Socket for the API
    PartOf=cri-docker.service
    [Socket]
    ListenStream=%t/cri-dockerd.sock
    SocketMode=0660
    SocketUser=root
    SocketGroup=docker
    [Install]
    WantedBy=sockets.target
    EOF

    systemctl daemon-reload
    systemctl enable cri-docker.service
    systemctl enable --now cri-docker.socket
    ```

4. Install Kubernetes

    ```bash
    # Add Kubernetes GPG key
    curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-archive-keyring.gpg

    # Add Kubernetes apt repository
    echo "deb [signed-by=/etc/apt/keyrings/kubernetes-archive-keyring.gpg] https://apt.kubernetes.io/ kubernetes-xenial main" | sudo tee /etc/apt/sources.list.d/kubernetes.list

    # Fetch package list
    sudo apt-get update

    sudo apt-get install -y kubelet kubeadm kubectl

    # Prevent them from being updated automatically
    sudo apt-mark hold kubelet kubeadm kubectl
    ```

5. Disable Swap

   ```bash
   sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab
   sudo swapoff -a
   ```

6. Forward IP Traffic

    ```bash
    sudo modprobe overlay
    sudo modprobe br_netfilter

    sudo tee /etc/sysctl.d/kubernetes.conf<<EOF
    net.bridge.bridge-nf-call-ip6tables = 1
    net.bridge.bridge-nf-call-iptables = 1
    net.ipv4.ip_forward = 1
    EOF

    sysctl --system
    ```

7. Create the Cluster

    ```bash
    sudo kubeadm init --pod-network-cidr=10.244.0.0/16 --cri-socket unix:///var/run/cri-dockerd.sock
    ```

8. Configure Kubectl

    ```bash
    mkdir -p $HOME/.kube
    sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
    sudo chown $(id -u):$(id -g) $HOME/.kube/config
    ```

9. Install CNI

    ```bash
    kubectl apply -f https://raw.githubusercontent.com/coreos/flannel/master/Documentation/kube-flannel.yml
    ```

Kubernetes should now be fully functional as a standalone single node cluster and you can run commands against it using kubectl.

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
