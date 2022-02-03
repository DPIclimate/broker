#
# TODO:
#
# Consider the ability to update a device on TTN based upon broker information, or the
# other way around. Where is the source of truth?
#

import json
import db.DAO as dao
import api.client.Ubidots as ubi
from typing import Optional
from pdmodels.Models import LogicalDevice, PhysicalDevice, PhysicalToLogicalMapping, Location
import dateutil.parser


#
# This import does not need to run periodically because once the broker is running it creates
# new logical devices itself.
#

def create_all_devices():
    devs = ubi.get_all_devices()
    for d in devs:
        existing_dev_list = dao.get_logical_devices(query_args={'prop_name': ['id'], 'prop_value': [d.properties['id']]})
        if len(existing_dev_list) > 0:
            print(f'Device exists: {existing_dev_list[0]}')
        else:
            print('Adding device to broker')
            dao.create_logical_device(d)


def find_match(pd: PhysicalDevice) -> Optional[LogicalDevice]:
    dev_eui = pd.properties['dev_eui']
    l_dev_list = dao.get_logical_devices(query_args={'prop_name': ['label'], 'prop_value': [dev_eui]})
    l_dev_list_len = len(l_dev_list)
    if l_dev_list_len == 0:
        #print(f'No ubidots device found for {pd.name}: {json.dumps(pd.properties)}')
        return None
    elif l_dev_list_len > 1:
        #print(f'Found {l_dev_list_len} devices for dev_eui / label {dev_eui}, name = {pd.name}')
        return None
    
    return l_dev_list[0]


def match_devices():
    p_dev_list = dao.get_physical_devices()
    for pd in p_dev_list:
        ld = find_match(pd)
        if ld is None:
            continue

        # Mark the mapping as started when the Ubidots device was created.
        # That is when it received the first message from TTN.
        start_time = dateutil.parser.isoparse(ld.properties['createdAt'])

        mapping = PhysicalToLogicalMapping(pd=pd, ld=ld, start_time=start_time)
        dao.insert_mapping(mapping)


def show_mappings():
    p_dev_list = dao.get_physical_devices()
    for pd in p_dev_list:
        mapping = dao.get_current_device_mapping(pd=pd)
        if mapping is None:
            print(f'NO MAP FOR {pd}')
        else:
            print(f'{pd.name} --> {mapping.ld.name} from {mapping.start_time}')


if __name__ == "__main__":
    show_mappings()


"""
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
  "lastActivity": 1643827288181,
  "createdAt": "2021-09-13T00:31:23.059326Z",
  "variables": "https://industrial.api.ubidots.com/api/v2.0/devices/613e9bdbf4c81a040178e28c/variables",
  "variablesCount": 24
}
"""