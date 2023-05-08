#! /usr/bin/python3

from datetime import datetime
import influxdb_client, os, time
from influxdb_client import InfluxDBClient, Point, WriteOptions, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import json

#variables for connecting to the db
token = os.environ.get("INFLUXDB_TOKEN")
org = "ITC303"
url = "http://localhost:8086"

#connect to the db
client = influxdb_client.InfluxDBClient(url=url, token=token, org=org)

#create bucket for data storage
bucket="DPI"

#create a writeAPI client
write_api = client.write_api(write_options=SYNCHRONOUS)

#define a function to parse json message and convert to influxdb line protocol
def json_to_line_protocol(json_msg):
  parsed_msg = json.loads(json_msg)
  l_uid = parsed_msg['l_uid']
  p_uid = parsed_msg['p_uid']
  timestamp = parsed_msg['timestamp']
  ts_datetime = datetime.fromisoformat(timestamp)
  ts = int(ts_datetime*1000)
  measurements = parsed_msg['timeseries']
  lines = []
  for measurement in measurements:
    measurement_name = measurement['name']
    measurement_value = measurement['value']
    line = f"{measurement_name},l_uid={l_uid},p_uid={p_uid} value={measurement_value} {int(ts.timestamp()*1000)}"
    lines.append(line)
  return "\n".join(lines)


#open json file
with open("../../docs/sample_messages", "r") as f:
  json_msgs = f.readlines()
  lines = [json_to_line_protocol(msg) for msg in json_msgs]

#write lines
write_api = client.write_api(write_options=WriteOptions(batch_size=100, flush_interval=500, jitter_interval=400, retry_interval = 2500))
write_api.write(bucket=bucket, org=org, record=lines, write_precision='ms')

#example json msg
#
#{
# "broker_correlation_id": "83d04e6f-db16-4280-53f11b2335c6",
# "p_uid": 301,
# "l_uid": 276,
# "timestamp": "2023-01-30T06:21:56Z",
# "timeseries": [
#   {
#   "name": "battery (v)",
#   "value": 4.16008997
#   },
#   {
#   "name": "pulse_count",
#   "value": 1
#   },
#   {"name": "1_Temperature",
#   "value": 21.60000038
#   }
# ]
#}

query_api = client.query_api()

query = """from(bucket: "DPI")
  |> range(start: 0, stop: now())"""
tables = query_api.query(query, org="ITC303")

for table in tables:
  for record in table.records:
    print(record)


