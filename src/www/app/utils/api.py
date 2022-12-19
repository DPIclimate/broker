import json
import requests
import os
from datetime import datetime
import base64


end_point = os.environ['end_point']
bearer_token = os.environ['bearer_token']

# end_point = 'https://staging.farmdecisiontech.net.au'
# bearer_token = 'bad_token'


# Physical Device Links
physical_link_all = end_point + \
    '/broker/api/physical/devices/?include_properties=false'
physical_link_notes = end_point + '/broker/api/physical/devices/notes/'
physical_link_uid = end_point + '/broker/api/physical/devices/'
physical_link_update = end_point + '/broker/api/physical/devices/'

# Logical Device Links
logical_link_all = end_point + '/broker/api/logical/devices/?include_properties=false'
logical_link_uid = end_point + '/broker/api/logical/devices/'
logical_link_insert = end_point + '/broker/api/logical/devices/'
logical_link_update = end_point + '/broker/api/logical/devices/'

# Mapping Device Links
physical_link_unmapped = end_point + '/broker/api/physical/devices/unmapped/'
physical_link_endmapping = end_point + '/broker/api/mappings/physical/end/'
logical_link_endmapping = end_point + '/broker/api/mappings/logical/end/'
mapping_link_all = end_point + '/broker/api/mappings/logical/all/'
mapping_link_current = end_point + '/broker/api/mappings/physical/current/'
mapping_link_insert = end_point + '/broker/api/mappings/'

# Other links
note_link_insert = end_point + '/broker/api/physical/devices/notes/'
delete_note_url = end_point + '/broker/api/physical/devices/notes/'
sources_link_all = end_point + '/broker/api/physical/sources/'
login_url = f"{end_point}/broker/api/token"


def get_sources(token: str):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(sources_link_all, headers=headers).raise_for_status()
    
    return response.json()


def get_physical_devices(token: str):
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(physical_link_all, headers=headers).raise_for_status()

    return response.json()


def get_physical_notes(uid: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(physical_link_notes + str(uid), headers=headers).raise_for_status()
    return response.json()


def get_logical_devices(token: str):
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(logical_link_all, headers=headers).raise_for_status()
    return response.json()


def get_physical_unmapped(token: str):
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(physical_link_unmapped, headers=headers).raise_for_status()
    return response.json()


def get_physical_device(uid: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(physical_link_uid + str(uid), headers=headers).raise_for_status()

    return response.json()


def get_logical_device(uid: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(logical_link_uid + str(uid), headers=headers).raise_for_status()
    return response.json()


def get_device_mappings(uid: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(mapping_link_all + str(uid), headers=headers).raise_for_status()
    return response.json()


def get_current_mappings(uid: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(mapping_link_current + str(uid), headers=headers).raise_for_status()
    return response.json()


def update_physical_device(uid: str, name: str, location: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    device = get_physical_device(uid)
    device['name'] = name
    device['location'] = location
    response = requests.patch(physical_link_update,
                              headers=headers, json=device).raise_for_status()
    return response.json()


def update_logical_device(uid: str, name: str, location: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    device = get_logical_device(uid)
    device['name'] = name
    device['location'] = location
    response = requests.patch(
        logical_link_update, headers=headers, json=device).raise_for_status()

    return response.json()


def end_logical_mapping(uid: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    url = logical_link_endmapping + uid
    requests.patch(url, headers=headers).raise_for_status()


def end_physical_mapping(uid: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    url = physical_link_endmapping + uid
    requests.patch(url, headers=headers).raise_for_status()


def create_logical_device(data, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    timeObject = datetime.now()
    logicalJson = {
        "uid": 0,
        "name": data['name'],
        "location": data['location'],
        "last_seen": str(timeObject),
        "properties": data['properties']
    }
    response = requests.post(
        logical_link_insert, json=logicalJson, headers=headers).raise_for_status()

    logical_device = response.json()
    return logical_device['uid']


def delete_note(uid: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    baseUrl = delete_note_url + str(uid)
    response = requests.delete(baseUrl, headers=headers)
    response.raise_for_status()

    return response.json()


def insert_device_mapping(physicalUid: str, logicalUid: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    logicalDevice = get_logical_device(logicalUid)
    physicalDevice = get_physical_device(physicalUid)
    timeObject = datetime.now()
    end_physical_mapping(physicalUid)
    mappingJson = {
        "pd": {
            "uid": physicalDevice['uid'],
            "source_name": physicalDevice['source_name'],
            "name": physicalDevice['name'],
            "location": physicalDevice['location'],
            "last_seen": physicalDevice['last_seen'],
            "source_ids": physicalDevice['source_ids'],
            "properties": physicalDevice['properties']
        },
        "ld": {
            "uid": logicalDevice['uid'],
            "name": logicalDevice['name'],
            "location": logicalDevice['location'],
            "last_seen": logicalDevice['last_seen'],
            "properties": logicalDevice['properties']
        },
        "start_time": str(timeObject),
        "end_time": str(timeObject)
    }
    response = requests.post(
        mapping_link_insert, json=mappingJson, headers=headers).raise_for_status()
    
    return response.json()


def insert_note(noteText: str, uid: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    noteJson = {
        "note": noteText
    }
    baseUrl = note_link_insert + uid
    response = requests.post(baseUrl, json=noteJson, headers=headers).raise_for_status()

    return response.json()


def edit_note(noteText: str, uid: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    timeObject = datetime.now()
    noteJson = {
        "uid": int(uid),
        "ts": str(timeObject),
        "note": str(noteText)
    }
    baseUrl = note_link_insert
    response = requests.patch(baseUrl, json=noteJson, headers=headers).raise_for_status()
    return response.json()


def format_json(data):
    return (json.dumps(data, indent=4, sort_keys=True))


def get_user_token(username: str, password: str):

    headers = {"Authorization": f"Basic {base64.b64encode(f'{username}:{password}'.encode()).decode()}"}
    
    response = requests.get(login_url, headers=headers).raise_for_status()

    return response.json()
