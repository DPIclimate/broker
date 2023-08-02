#!/usr/bin/env bash
docker stop -f $(docker ps -aq)
docker rm -f $(docker ps -aq)

