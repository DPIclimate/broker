import requests
import json
import os

BASE = "https://eu1.cloud.thethings.network/api/v3/applications"


headers = {
    "Authorization":os.environ['TTN_API_TOKEN'],
}


#Json data used for registing a new device
newDeviceData = {"end_device":{
        "ids": {
            "device_id": "",
            "application_ids": {
                "application_id": ""
            },
            "dev_eui": "",
            "join_eui": "0000000000000000"
        },
        "network_server_address": "au1.cloud.thethings.network",
        "application_server_address": "au1.cloud.thethings.network",
        "join_server_address": "au1.cloud.thethings.network",
        "field_mask":{
            "paths":["network_server_address","application_server_address","join_server_address"]
        }
    }
}


def get_device_details(applicationID, deviceID):
    # Get details of a particular device

    url = f"{BASE}/{applicationID}/devices/{deviceID}?field_mask=name,description,locations,attributes"
    r = requests.get(url, headers=headers)
    r_json = json.loads(r.content)

    return r_json


def get_devices(applicationID):
    #Get devices in application

    url = f"{BASE}/{applicationID}/devices?field_mask=name,description,locations"
    r = requests.get(url, headers=headers)

    r_json = json.loads(r.content)
    return r_json


def register_device(applicationID, deviceName):
    # Register a device with TTN

    url=f"{BASE}/{applicationID}/devices"
    # print(url)
    
    # json_object = getEui(applicationID)
    dev_eui = json.loads(json_object)["dev_eui"].lower()

    # Set new identifiers
    newDeviceData["end_device"]["ids"]["dev_eui"] = dev_eui
    newDeviceData["end_device"]["ids"]["device_id"] = f"{deviceName}-UID"
    newDeviceData["end_device"]['ids']["application_ids"]["application_id"] = applicationID

    #Convert to json object otherwise requests will urlencode
    payload = json.dumps(newDeviceData)
    r = requests.post(url, headers=headers, data=payload)

    print(r.status_code)
    print(r.text)


def get_eui(applicationID):
    #Request a new eui from ttn

    url = f"{BASE}/{applicationID}/dev-eui"
    r = requests.post(f"{BASE}/{applicationID}/dev-eui", headers=headers)
    return r.text


def get_application(applicationID):

    url = f"{BASE}/{applicationID}"

    r = requests.get(url, headers=headers)
    r_json = json.loads(r.content)
    return r_json


def get_applications():

    url = f"{BASE}"
    print(url)
    r = requests.get(url, headers=headers)
    r_json = json.loads(r.content)
    return r_json


def main():

    print(get_applications())


if __name__ == "__main__":
    main()
