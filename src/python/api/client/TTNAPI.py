import requests
import json
import os

BASE = "https://eu1.cloud.thethings.network/api/v3/applications"


headers = {
    "Authorization":os.environ['TTN_API_TOKEN'],
}


def get_device_details(applicationID, deviceID):
    url = f"{BASE}/{applicationID}/devices/{deviceID}?field_mask=name,description,locations,attributes"
    r = requests.get(url, headers=headers)
    r_json = json.loads(r.content)
    return r_json


def get_devices(applicationID):
    url = f"{BASE}/{applicationID}/devices?field_mask=name,description,locations"
    r = requests.get(url, headers=headers)
    r_json = json.loads(r.content)
    return r_json


def get_application(applicationID):
    url = f"{BASE}/{applicationID}"
    r = requests.get(url, headers=headers)
    r_json = json.loads(r.content)
    return r_json


def get_applications():
    url = f"{BASE}"
    r = requests.get(url, headers=headers)
    r_json = json.loads(r.content)
    return r_json


def main():
    print(get_applications())


if __name__ == "__main__":
    main()
