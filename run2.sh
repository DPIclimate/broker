#!/usr/bin/env bash

CWD="$(pwd)"

#add our nginx container stuff
NGINX_ROOT=$(
	cd 303/nginx
	pwd
)
cd $NGINX_ROOT
docker ps | grep -q "nginx-t" >>/dev/null && docker stop nginx-t >>/dev/null && echo "Stopping nginx-t"
docker ps -a | grep -q "nginx-t" >>/dev/null && docker rm nginx-t >>/dev/null
docker images -a | grep -q "nginx_img" >>/dev/null && docker rmi nginx_img >>/dev/null
docker images -a | grep -q "nginx" || docker pull nginx && echo "pulling nginx image"
docker build -q -t nginx_img .
docker run --name nginx-t -p 80:80 -d nginx_img:latest >>/dev/null
echo "starting nginx container"
docker start nginx-t >>/dev/null
docker ps | grep -q 'nginx-t' && echo 'nginx-t started'

#run the actual run
cd $CWD
echo "starting broker containers"
./run.sh "$@"
