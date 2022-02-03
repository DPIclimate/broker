from typing import List
from urllib import response
import requests
import asyncio, datetime, functools, json, logging, os, time

from pdmodels.Models import Location, LogicalDevice

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
logger = logging.getLogger(__name__)

BASE_1_6 = "https://industrial.api.ubidots.com/api/v1.6"
BASE_2_0 = "https://industrial.api.ubidots.com/api/v2.0"


headers = {
    "X-Auth-Token": os.environ['UBIDOTS_API_TOKEN'],
}

"""
Example Ubidots JSON device definition:

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
def get_all_devices() -> List[LogicalDevice]:
    page = 1
    devices = []

    while True:
        url = f'{BASE_2_0}/devices/?page={page}'
        r = requests.get(url, headers=headers)
        logger.info(r.status_code)
        if r.status_code != 200:
            logger.warn(f'devices/ received response: {r.status_code}: {r.reason}')
            logger.warn('Returning before all devices were retrieved.')
            break

        response_obj = json.loads(r.content)
        logger.info(f'Adding {len(response_obj["results"])} devices to array.')

        for u in response_obj['results']:
            last_seen_sec = u['lastActivity'] / 1000
            last_seen = datetime.datetime.fromtimestamp(last_seen_sec)

            location = None
            if '_location_fixed' in u['properties']:
                uloc = u['properties']['_location_fixed']
                location = Location(lat=uloc['lat'], long=uloc['lng'])

            log_dev = LogicalDevice(name=u['name'], last_seen=last_seen, location=location, properties=u)
            #if location is not None:
            #    print(json.dumps(u, indent=2))
            #    print(log_dev)

            devices.append(log_dev)

        if response_obj['next'] is None:
            break
            
        page += 1

        # Don't upset ubidots with too many calls per second.
        time.sleep(1)

    return devices


def main():
    devs = get_all_devices()
    print(len(devs))


if __name__ == '__main__':
    main()
