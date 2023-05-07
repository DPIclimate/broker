#! /usr/bin/python3

import influxdb_client, os, time
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import json
from time import gmtime, strftime
from datetime import datetime
from dateutil import parser

token = os.environ.get("INFLUXDB_TOKEN")
org = "ITC303"
url = "http://localhost:8086"

client = influxdb_client.InfluxDBClient(url=url, token=token, org=org)

bucket="DPI"

write_api = client.write_api(write_options=SYNCHRONOUS)

def parse_input_file() -> None:
  f = open("../../docs/sample_messages", "r")
  l = f.readlines()
  for line in l:
    parse_json_msg(json.loads(line))

def parse_json_msg(msg: str) -> None:
  measurement = 1
  tag1 = 1
  tagvalue1 = 1
  tag2 = 1
  tagvalue2 = 1
  field1 = 1
  fieldvalue1 = 1
  timestamp = parser.parse(msg['timestamp'])
  insert_msg(measurement,tag1,tagvalue1,tag2,tagvalue2,field1,fieldvalue1,timestamp)
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

def insert_msg(measurement,tag1,tagvalue1,tag2,tagvalue2,field1,fieldvalue1,timestamp):
  point = (
    Point(measurement)
    .tag("tagname1", "tagvalue1")
    .field("field1", value)
    .time("timestamp")
  )
  write_api.write(bucket="DPI", org="ITC303", record=point)
  time.sleep(1) # separate points by 1 second

query_api = client.query_api()

query = """from(bucket: "DPI")
  |> range(start: 2023-04-01T00:00:00z)
  |> filter(fn: (r) => r._measurement == "1")"""
tables = query_api.query(query, org="ITC303")

for table in tables:
  for record in table.records:
    print(record)


