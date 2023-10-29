#!/usr/bin/env bash

user="user"
pass="pass"
num_devices=10
container_name="test-lm-1"

# Check if prod container running
if docker ps -a --format "{{.Names}}" | grep -q "^prod-lm-1$"; then
	container_name="prod-lm-1"
fi

#get users
users=$(docker exec "$container_name" python -m broker-cli users ls | tr -d "[]'")
IFS=',' read -r -a array <<<"${users}"

#check if user exists then create it if it doesnt
if echo "${array[@]}" | grep -q -w "$user"; then
	echo "user already"
else
	echo 'adding user'
	docker exec "$container_name" python -m broker-cli users add -u "${user}" -p "${pass}"
	users=$(docker exec "$container_name" python -m broker-cli users ls)
	echo "listed users: ${users}"
	echo "login with ${user} && ${pass}"
fi

#generate 10 lots of devices add them and map them
counter=1
puids=()
echo "adding devices and mappings"
while [ $counter -le $num_devices ]; do
	dev_name="Test Sensor $counter"
	longi=$(awk 'BEGIN{srand();printf"%.4f",501.0+rand()*10.0}') #somewhat nsw
	lati=$(awk 'BEGIN{srand();printf"%.4f",29.0+rand()*7.0}')    #somewhat nsw
	app_id="ttn-app-id-$counter"
	dev_id="ttn-device-id-$counter"
	dev_eui="ttn-dev-eui-$counter"
	device_template='{
    "source_name": "ttn",
    "name": "'$dev_name'",
    "location": {
      "lat": "-'$lati'",
      "long": "'$longi'"
    },
    "source_ids": {
      "app_id": "'$app_id'",
      "dev_id": "'$dev_id'",
      "dev_eui": "'$dev_eui'"
    },
    "properties": {
      "description": "Sample Test Device Properties"
    }
  }'
	#echo "$device_template"
	puid=$(docker exec "$container_name" python -m broker-cli pd create --json "$device_template" | grep "uid" | sed 's/[^0-9]*//g')
	luid=$(docker exec "$container_name" python -m broker-cli ld create --json "$device_template" | grep -oP 'uid=\K\d+')
	docker exec "$container_name" python -m broker-cli map start --puid "$puid" --luid "$luid" >/dev/null
	puids+=("$puid")
	((counter++))
	echo -ne "."
done
echo

# print devices
#echo 'PHYSICAL DEVICES:'
#devices=$(docker exec "$container_name" python -m broker-cli pd ls --plain)
#echo -e "listed devices:\n${devices}"
#echo 'LOGICAL DEVICES:'
#devices=$(docker exec "$container_name" python -m broker-cli ld ls --plain)
#echo -e "listed devices:\n${devices}"
#echo 'MAPPINGS:'
#for puid in "${puids[@]}"; do
#	output=$(docker exec "$container_name" python -m broker-cli map ls --puid "$puid")
#	echo "$output" | jq -r '"pd uid:\(.pd.uid) -> ld uid:\(.ld.uid)"'
#done
