import json
import random
from datetime import datetime, timedelta

for i in range(100):
    broker_correlation_id = "83d04e6f-db16-4280-8337-53f11b2335c6"
    l_uid = random.randint(1, 10)  # Adjusted to be less than 10 as per your requirement
    p_uid = l_uid
    timestamp = (datetime.now() - timedelta(days=random.randint(0, 180), hours=random.randint(0, 23))).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    timeseries = [
        {"name": "gnss", "value": round(random.uniform(1, 30), 1)},
        {"name": "Battery (V)", "value": round(random.uniform(1, 20), 1)},
        {"name": "S1_EC", "value": round(random.uniform(1, 30), 1)},
        {"name": "vt", "value": round(random.uniform(500, 5000), 1)},
        {"name": "s4solarRadiation", "value": round(random.uniform(1, 30), 1)},
        {"name": "Battery (A)", "value": round(random.uniform(1, 20), 1)},
        {"name": "1_Temperature", "value": round(random.uniform(-10, 40), 1)},
        {"name": "S1_Temp_50cm", "value": round(random.uniform(1, 30), 1)},
        {"name": "windDirection", "value": round(random.uniform(1, 8000), 1)}
    ]
    
    message = {
        "broker_correlation_id": broker_correlation_id,
        "l_uid": l_uid,
        "p_uid": p_uid,
        "timestamp": timestamp,
        "timeseries": timeseries
    }
    
    print(json.dumps(message))


