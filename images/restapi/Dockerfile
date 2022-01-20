# Using the alpine-based image avoids the psycopg2/libpq problem the work-around
# below addresses, but it is very slow to build the pip install step. That image
# is cached so it only has an effect if the pip install line changes.
FROM python:3-alpine3.10

# For ubuntu-based images
#RUN groupadd broker && useradd -m -g broker broker

# For alpine-based images
RUN addgroup -S broker && adduser -S broker -G broker

USER broker

RUN pip install --user --progress-bar off --upgrade pip
RUN pip install --user --progress-bar off psycopg2-binary fastapi[all]

# Work-around on ubuntu-based image, probably only works on (and required by) M1-based macos.
# Fix a broken ARM psycopg2-binary installation by copying a later libpq from the system.
#WORKDIR /home/broker/.local/lib/python3.10/site-packages/psycopg2_binary.libs/
#RUN cp libpq-d97d8807.so.5.9 libpq-d97d8807.so.5.9.org
#RUN cp /usr/lib/aarch64-linux-gnu/libpq.so.5.13 libpq-d97d8807.so.5.9

WORKDIR /home/broker/app

EXPOSE 5687

ENTRYPOINT [ "/home/broker/.local/bin/uvicorn", "--reload", "--host", "0.0.0.0", "--port", "5687", "RestAPI:app" ]
