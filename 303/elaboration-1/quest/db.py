from questdb.ingress import Sender, IngressError
import requests
import json
import sys
from dateutil import parser


def create_table() -> int:
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


def parse_input_file() -> None:
    f = open("../../docs/sample_messages", "r")
    l = f.readlines()
    for line in l:
        parse_json_msg(json.loads(line))


def parse_json_msg(msg: str) -> None:
    #syms = {"p_uid" : f'{msg["p_uid"]}', "l_uid" : f'{msg["l_uid"]}'}
    syms = {}
    cols = {item['name'].replace("(","").replace(")","").replace('-','_').replace('/',''):item['value'] for item in msg["timeseries"]}
    cols["p_uid"] = msg["p_uid"]
    cols["l_uid"] = msg["l_uid"]
    ts = parser.parse(msg['timestamp'])
    insert_jason_msg(syms, cols, ts)


def insert_jason_msg(syms: str, cols: str, timestamp: str) -> None:
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


def get_all_inserts() -> str:
    name = "dpi"
    host = "localhost"
    port = 9000

    return requests.get(
        f'http://{host}:{port}/exec',
        {
            'query':'dpi ORDER BY l_uid;'
        }
    ).text


#ret = create_table()
#if ret == 200 or ret == 400:
parse_input_file()
print('getting data from dpi db')
print(json.dumps(json.loads(get_all_inserts()), indent=2))


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

