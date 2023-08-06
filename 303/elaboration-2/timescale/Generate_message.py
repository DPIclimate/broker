import random


def random_msg() -> str:
    rand_cor_id = random.randint(100000, 9999999)
    rand_id = random.randint(1, 200)
    rand_id2 = random.randint(1, 400)
    rand_value = random.randint(0, 30)
    rand_value2 = random.randint(0, 10)

    msg = f"""{{
  "broker_correlation_id": "{rand_cor_id}",
  "p_uid": {rand_id},
  "l_uid": {rand_id2},
  "timestamp": "2023-01-30T06:21:56Z",
  "timeseries": [
    {{
    "name": "battery (v)",
    "value": {rand_value}
    }},
    {{
    "name": "pulse_count",
    "value": {rand_value2}
    }}
  ]
}}"""

    return msg

if __name__ == "__main__":
    print(random_msg())