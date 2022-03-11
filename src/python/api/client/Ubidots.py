from typing import List
import requests
import datetime, json, logging, os, time

from pdmodels.Models import Location, LogicalDevice

BASE_1_6 = "https://industrial.api.ubidots.com/api/v1.6"
BASE_2_0 = "https://industrial.api.ubidots.com/api/v2.0"


headers = {
    "X-Auth-Token": os.environ['UBIDOTS_API_TOKEN'],
}

"""
Example Ubidots JSON device definition FROM THE 2.0 API! The field names are different between the 1.6 and 2.0 APIs.

{
    "url": "https://industrial.api.ubidots.com/api/v2.0/devices/613e9bdbf4c81a040178e28c",
    "id": "613e9bdbf4c81a040178e28c",
    "organization": {
      "url": "https://industrial.api.ubidots.com/api/v2.0/organizations/6166081792fbf603ba4ab476",
      "id": "6166081792fbf603ba4ab476",
      "label": "orange-agricultural-institute-1",
      "name": "Orange Agricultural Institute",
      "createdAt": "2021-10-12T22:11:35.161514Z"
    },
    "label": "00bac91837e6a3de",
    "name": "OAI-BOM-2149-AWS",
    "description": "BoM Yard AWS",
    "tags": [],
    "properties": {
      "_icon": "snowflake",
      "appId": "aws-ict-atmos41",
      "devId": "oai-bom-2149",
      "_color": "#12d2f1",
      "source": "ttn",
      "_config": {},
      "_device_type": "atmos41",
      "_location_type": "manual",
      "_location_fixed": {
        "lat": -33.320932,
        "lng": 149.082804
      }
    },
    "isActive": true,
    "lastActivity": 1643775074171,
    "createdAt": "2021-09-13T00:31:23.059326Z",
    "variables": "https://industrial.api.ubidots.com/api/v2.0/devices/613e9bdbf4c81a040178e28c/variables",
    "variablesCount": 24
}
"""

def _dict_to_logical_device(ubidots_dict) -> LogicalDevice:
    """
    This method assumes the JSON returned from an API 2.0 call.
    """
    logging.debug(f'dict from ubidots: {ubidots_dict}')

    last_seen = datetime.datetime.now(datetime.timezone.utc)
    if 'lastActivity' in ubidots_dict:
        last_seen_sec = ubidots_dict['lastActivity'] / 1000
        last_seen = datetime.datetime.fromtimestamp(last_seen_sec)

    location = None
    if 'properties' in ubidots_dict:
        if '_location_fixed' in ubidots_dict['properties']:
            uloc = ubidots_dict['properties']['_location_fixed']
            location = Location(lat=uloc['lat'], long=uloc['lng'])

    return LogicalDevice(name=ubidots_dict['name'], last_seen=last_seen, location=location, properties={'ubidots': ubidots_dict})


def get_all_devices() -> List[LogicalDevice]:
    page = 1
    devices = []

    while True:
        time.sleep(0.3)
        url = f'{BASE_2_0}/devices/?page={page}'
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            logging.warn(f'devices/ received response: {r.status_code}: {r.reason}')
            logging.warn('Returning before all devices were retrieved.')
            break

        response_obj = json.loads(r.content)
        logging.debug(f'Adding {len(response_obj["results"])} devices to array.')

        for u in response_obj['results']:
            devices.append(_dict_to_logical_device(u))

        if response_obj['next'] is None:
            break
            
        page += 1

    return devices


def get_device(label: str) -> LogicalDevice:
        url = f'{BASE_2_0}/devices/~{label}'
        time.sleep(0.3)
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            logging.warn(f'devices/~{label} received response: {r.status_code}: {r.reason}')
            return None

        response_obj = json.loads(r.content)
        return _dict_to_logical_device(response_obj)


def post_device_data(label: str, body) -> None:
    """
    Post timeseries data to an Ubidots device.

    label must be the device label, not the device id.
    body must be a dict in the format of:
        {
        'battery': {'value': 3.6, 'timestamp': 1643934748392},
        'humidity': {'value': 37.17, 'timestamp': 1643934748392},
        'temperature': {'value': 37.17, 'timestamp': 1643934748392}
        }
    """
    url = f'{BASE_1_6}/devices/{label}'
    hdrs = headers
    hdrs['Content-Type'] = 'application/json'
    body_str = json.dumps(body)
    time.sleep(0.3)
    r = requests.post(url, headers=hdrs, data=body_str)
    if r.status_code != 200:
        logging.warning(f'POST {url}: {r.status_code}: {r.reason}')


def update_device(label: str, patch_obj) -> None:
    url = f'{BASE_2_0}/devices/~{label}'
    time.sleep(0.3)
    response = requests.patch(url, headers=headers, json=patch_obj)
    if response.status_code != 200:
        logging.warning(f'PATCH response: {response.status_code}: {response.reason}')


def main():
    pass


if __name__ == '__main__':
    main()
