FROM node:16-bullseye

RUN mkdir -p /usr/src/ttn_decoder
WORKDIR /usr/src/ttn_decoder
RUN npm init -y
RUN npm install body-parser express morgan prom-client

ENTRYPOINT [ "/usr/src/ttn_decoder/bin/run.sh" ]
