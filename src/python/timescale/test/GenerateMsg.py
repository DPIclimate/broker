import random

def test_msg():
    cor_id = "test_id"
    p_uid = "phys_id"
    l_uid = "log_id"
    value = "first_value"
    value2 = "second_value"

    msg = f"""{{
    "broker_correlation_id": "{cor_id}",
    "p_uid": {p_uid},
    "l_uid": {l_uid},
    "timestamp": "2023-01-30T06:21:56Z",
    "timeseries": [
      {{
      "name": "battery (v)",
      "value": {value}
      }},
      {{
      "name": "pulse_count",
      "value": {value2}
      }}
    ]
  }}"""

    return msg

def random_msg(newvalue: str = '', newvalue2: str = '') -> str:
    cor_id = random.randint(100000, 9999999)
    p_uid = random.randint(1, 200)
    l_uid = random.randint(1, 400)
    value = str(random.randint(0, 30))
    value2 = str(random.randint(0, 10))

    if newvalue != '':
        value = newvalue

    if newvalue2 != '':
        value2 = newvalue2

    msg = f"""{{
    "broker_correlation_id": "{cor_id}",
    "p_uid": {p_uid},
    "l_uid": {l_uid},
    "timestamp": "2023-01-30T06:21:56Z",
    "timeseries": [
      {{
      "name": "battery (v)",
      "value": "{value}"
      }},
      {{
      "name": "pulse_count",
      "value": "{value2}"
      }}
      ]
    }}"""

    return msg

def random_msg_single(newvalue: str = '') -> str:
    cor_id = random.randint(100000, 9999999)
    p_uid = random.randint(1, 400)
    l_uid = random.randint(1, 500)
    value = str(random.randint(0, 45))

    if newvalue != '':
        value = newvalue

    msg = f"""{{
    "broker_correlation_id": "{cor_id}",
    "p_uid": {p_uid},
    "l_uid": {l_uid},
    "timestamp": "2023-01-30T06:21:56Z",
    "timeseries": [
      {{
      "name": "battery (v)",
      "value": "{value}"
      }}
      ]
    }}"""

    return msg

if __name__ == "__main__":
    print(random_msg())