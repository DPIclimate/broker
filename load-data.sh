#!/usr/bin/env bash

user="user"
pass="pass"
devices=("testdev1.json" "testdev2.json")

users=$(docker exec test-lm-1 python -m broker-cli users ls | tr -d "[]'")
IFS=',' read -r -a array <<< "${users}"

#check if user exists then create it if it doesnt
if echo "${array[@]}" | grep -q -w "$user"; then
    echo "user already"
else
    echo 'adding user'
    docker exec test-lm-1 python -m broker-cli users add -u "${user}" -p "${pass}"
    users=$(docker exec test-lm-1 python -m broker-cli users ls)
    echo "listed users: ${users}"
    echo "login with ${user} && ${pass}"
fi

#load our devices
for device in "${devices[@]}"; do
  echo "adding test device: $device"
  docker exec test-lm-1 python -m broker-cli pd create --file $device > /dev/null
done
# print devices 
devices=$(docker exec test-lm-1 python -m broker-cli pd ls --plain)
echo -e "listed devices:\n${devices}"
