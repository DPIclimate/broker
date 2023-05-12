# Requirements

*In addition to the requirements required for launching the application on Docker-Compose*

### minikube

- is the tool for setting up a local Kubernetes environment on your local device
- `minikube` available at https://minikube.sigs.k8s.io/docs/start/

### kubectl

- is the command line tool to control Kubernetets
- `kubectl` available at https://kubernetes.io/docs/tasks/tools/

# Repository

Each microservice from the `docker-compose.yml` has been converted to its own Kubernetes YAML file.

This currently translates to 14 YAML files available under the `broker/kubernetes` folder in the `feature/kubernetes`
branch.

#### 12 files for the microservices

- `db.yaml`
- `delivery.yaml`
- `frred.yaml`
- `lm.yaml`
- `mq.yaml`
- `restapi.yaml`
- `ttn_decoder.yaml`
- `ttn_processor.yaml`
- `ttn_webhook.yaml`
- `website.yaml`
- `wombat.yaml`
- `ydoc.yaml`

#### 1 file for environment variables

- `env-configmap.yaml`

#### 1 file carried over from test development

- `x.yaml`

# Start Kubernetes

The following command will start your Kubernetes environment with a single node (you should be able to see this node as
a container in Docker Desktop):

- `minikube start`

# Use local Docker images

To use local Docker images (instead of pulling them from DockerHub), you will need to direct `minikube` to point to your
local Docker daemon. After this you will also need to rebuild each Docker image you will be using locally.

*Note: this will need to be done each time the `minikube` node is started.*

To redirect `minikube` to the Docker daemon:

- `eval $(minikube -p minikube docker-env) `

To rebuild each of the three local Docker images (you will need to be in the `broker` folder):

- `docker build -t broker/python-base -f images/restapi/Dockerfile .`
- `docker build -t broker/ttn_decoder -f images/ttn_decoder/Dockerfile .`
- `docker build -t broker/mgmt-app -f src/www/Dockerfile .`

# Mount local directories

Most of the microservices need to read from a particular directory in the `broker`, `ttn_formatter`, or `databolt` folders. These folders first need to be
made available to the node, where the node then mounts the relevant folder into the pod that requires it.

For my example I have these three directories as so on my local device:

- `/home/sam/csu-dpi/broker`
- `/home/sam/csu-dpi/ttn_formatters`
- `/home/sam/csu-dpi/databolt`

To mount these directories to the node, each command must be in its own terminal and the terminal must remain live (closing the terminal will close the mount)

- `minikube mount /home/sam/csu-dpi/broker:/home/broker`
- `minikube mount /home/sam/csu-dpi/ttn-formatters:/home/ttn-formatters`
- `minikube mount /home/sam/csu-dpi/databolt:/home/databolt`

*Note: leave the folder structure after the `:` as this is the expected structure the node and pods are reading from*

# Running the microservices

Change to the `kubernetes` directory and execute the following command to run all the YAML files within that folder:

- `kubectl apply -f .`

To view a dashboard of the node and pods, use this command:

- `minikube dashboard`

# To do

Create a script that starts the node, builds the images, mounts the directories, then starts the microservices.