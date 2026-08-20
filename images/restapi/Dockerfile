# This image is used for by Python containers in the broker.

# 3.10 is important. There is a breaking change in 3.11 where some dependencies have not
# been updated and cannot be built from source.
FROM python:3.10

# For debian-based images
RUN groupadd broker && useradd -m -g broker broker

# Two quiets here to suppress 'old version of pip' warning, given that is what is being upgraded.
RUN pip install --quiet --quiet --progress-bar off --upgrade pip

# Using a requirements.txt file to avoid breaking updates in modules.
COPY images/restapi/requirements.txt /tmp/requirements.txt
RUN pip install --progress-bar off --requirement /tmp/requirements.txt

USER broker
WORKDIR /home/broker/python/restapi

ENTRYPOINT [ "/bin/bash" ]
