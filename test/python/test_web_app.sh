#!/usr/bin/env bash

#MAKE SURE IOTA IS UP AND RUNNING
#REQUIRES RUNNING ../../load-data.sh OR AT LEAST HAVING SOME DEVICES WITH PUID AND LUID 1 IN THE SYSTEM
#
#RUN BY USING `./test_web_app.sh`
#CHECK RESULTS BY GOING TO IOTA WEB APP AND SELECTING ON EITHER PHYSICAL OR LOGICAL DEVICE #1 AND CHECK BOTTOM OF PAGE

iota_msgs=(
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-05T05:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 5.17719879313449},{"name": "battery voltage", "value": 12.17719879313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-05T06:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 18.59712346078412},{"name": "battery voltage", "value": 12.6313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-05T07:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 6.290074845534363},{"name": "battery voltage", "value": 12.19879313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-05T08:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 28.521567509813398},{"name": "battery voltage", "value": 12.7719879313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-05T09:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 13.335981939217794},{"name": "battery voltage", "value": 13.17719879313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-05T10:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 2.3252698879111664},{"name": "battery voltage", "value": 13.879313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-05T11:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 7.417581303815799},{"name": "battery voltage", "value": 13.19879313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-05T12:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 2.673679377416013},{"name": "battery voltage", "value": 12.313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-05T13:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 7.300519576905629},{"name": "battery voltage", "value": 11.9879313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-05T14:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 0.2999783007627932},{"name": "battery voltage", "value": 11.313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-06T05:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 5.17719879313449},{"name": "battery voltage", "value": 12.17719879313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-06T06:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 18.59712346078412},{"name": "battery voltage", "value": 12.6313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-07T07:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 6.290074845534363},{"name": "battery voltage", "value": 12.19879313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-07T08:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 28.521567509813398},{"name": "battery voltage", "value": 12.7719879313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-07T09:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 13.335981939217794},{"name": "battery voltage", "value": 13.17719879313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-08T10:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 2.3252698879111664},{"name": "battery voltage", "value": 13.879313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-08T11:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 7.417581303815799},{"name": "battery voltage", "value": 13.19879313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-08T12:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 2.673679377416013},{"name": "battery voltage", "value": 12.313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-08T13:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 7.300519576905629},{"name": "battery voltage", "value": 11.9879313449}]}'
	'{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": 1, "p_uid": 1, "timestamp":"2023-09-08T14:00:00.000000Z", "timeseries": [{"name": "5_Temperature", "value": 0.2999783007627932},{"name": "battery voltage", "value": 11.313449}]}'
)

send_msg() {
	local msg="$1"
	local exchange="lts_exchange"
	local queue="ltsreader_logical_msg_queue"
	local mq_user="broker"
	local mq_pass="CHANGEME"

	docker exec test-mq-1 rabbitmqadmin publish -u "$mq_user" -p "$mq_pass" \
		"exchange=$exchange" "routing_key=$queue" "payload=$msg" properties={}
}

for msg in "${iota_msgs[@]}"; do
	send_msg "$msg"
done
