# default message format
#
#{
#   "broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6",
#   "p_uid": 301,
#   "l_uid": 276,
#   "timestamp": "2023-01-30T06:21:56Z",
#   "timeseries": [
#       {
#       "name": "battery (v)",
#       "value": 4.16008997
#       },
#       {
#       "name": "pulse_count",
#       "value": 1
#       },
#       {
#       "name": "1_Temperature",
#       "value": 21.60000038
#       }
#   ]
#}

from questdb.ingress import Sender, IngressError
import requests
import json
import sys
from datetime import datetime
from dateutil import parser

json_msg ='{   "broker_correlation_od": "83d04e6f-db16-4280-8337-53f11b2335c6",\
   "p_uid": 301,\
   "l_uid": 276,\
   "timestamp": "2023-01-30T06:21:56Z",\
   "timeseries": [\
       {\
       "name": "battery (v)",\
       "value": 4.16008997\
       },\
       {\
       "name": "pulse_count",\
       "value": 1\
       },\
       {\
       "name": "1_Temperature",\
       "value": 21.60000038\
       }\
   ]\
}'

def create_table():
    query = 'CREATE TABLE dpi'\
            '(p_uid INT, l_uid INT, battery_v DOUBLE, pulse_count INT, temperature DOUBLE, ts TIMESTAMP)'\
            'timestamp(ts)'
    result = requests.get("http://localhost:9000/exec?query=" + query)
    if result.status_code == 200:
        print("table created")
    elif result.status_code == 400:
        print("table exists")
    else:
        print(f"error creating table : {result}")
    return result.status_code


def parse_input_file():
    f = open("../../docs/sample_messages", "r")
    l = f.readlines()
    for line in l:
        parse_json_msg(json.loads(line))


def parse_json_msg(msg):
    #syms = {"p_uid" : f'{msg["p_uid"]}', "l_uid" : f'{msg["l_uid"]}'}
    syms = {}
    cols = {item['name'].replace("(","").replace(")","").replace('-','_').replace('/',''):item['value'] for item in msg["timeseries"]}
    cols["p_uid"] = msg["p_uid"]
    cols["l_uid"] = msg["l_uid"]
    #ts = datetime.strptime(msg["timestamp"], '%Y-%m-%dT%H:%M:%SZ')
    ts = parser.parse(msg['timestamp'])
    insert_jason_msg(syms, cols, ts)


def insert_jason_msg(syms, cols, timestamp):
    name = "dpi"
    host = "localhost"
    port = 9009
    try:
        with Sender(host,port) as sender:
            sender.row(
                name,
                symbols=syms,
                columns=cols,
                at=timestamp
            )
            sender.flush()
    except IngressError as e:
        sys.stderr.write(f'error: {e}\n')

#ret = create_table()
#if ret == 200 or ret == 400:
parse_input_file()

#parse_json_msg(json.loads(json_msg))

