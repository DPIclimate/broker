"""
The Dumbat is a tool to test the Integration of the Intersect data wrangling code into
IoTa. It can read Wombat messages from a directory tree or an IoTa physical_timeseries table
and feed them to a Wombat receiver via MQTT.

The rate of message delivery can be specified to stress test the code.

"""

import logging
import BrokerConstants
import time
import math
import util.LoggingUtil as lu

from pathlib import Path
import os
import paho.mqtt.client as mqtt
from paho.mqtt.enums import MQTTErrorCode

mqtt_host = os.environ['RABBITMQ_HOST']
mqtt_port = 1883
mqtt_user = os.environ['RABBITMQ_DEFAULT_USER']
mqtt_password = os.environ['RABBITMQ_DEFAULT_PASS']

mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqttc.username_pw_set(mqtt_user, mqtt_password)

mqttc.loop_start()

mqttc.connect(mqtt_host, mqtt_port)
while not mqttc.is_connected():
    logging.warning('Not connected.')
    time.sleep(2)

logging.info('MQTT connected.')

msg_count = 0
sleep_time = 1 / 25

try:
    msg_root_dir = Path('scmn_msgs')
    for dirpath, dirnames, filenames in msg_root_dir.walk():
        dirnames.sort()
        for filename in filenames:
            if not filename.endswith('.json'):
                continue

            #logging.info(dirpath / filename)
            with open(dirpath / filename, 'rt') as fp:
                msg_text = fp.read()
                msg_info = mqttc.publish('wombat', msg_text, qos=1)
                msg_info.wait_for_publish()
                time.sleep(sleep_time)
                msg_count += 1
                if msg_count % 10000 == 0:
                    logging.info(f'Posted {msg_count} messages.')

finally:
    mqttc.disconnect()
    mqttc.loop_stop()
