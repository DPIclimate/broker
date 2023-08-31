import json
from typing import List
import requests
from datetime import datetime
import base64

from pdmodels.Models import PhysicalDevice, LogicalDevice, PhysicalToLogicalMapping, DeviceNote

end_point = 'http://restapi:5687'

def get_sources(token: str) -> List[str]:
    """
        Return list of sources

        Params:
            token: str - User's authentication token

        returns:
            sources: List[str] - A list of sources
    """
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(f'{end_point}/broker/api/physical/sources/', headers=headers)

    response.raise_for_status()

    return response.json()


def get_physical_devices(token: str, **kwargs) -> List[PhysicalDevice]:
    """
        Get all physical devices

        Params:
            token: str - User's authentication token

        returns:
            physical_devices: List[dict] - list of physical devices
    """
    headers = {"Authorization": f"Bearer {token}"}

    query_params = {'include_properties': False}
    for k, v in kwargs.items():
        if k == 'source_name':
            query_params[k] = v
        elif k == 'include_properties':
            query_params[k] = v

    response = requests.get(f"{end_point}/broker/api/physical/devices/", params=query_params, headers=headers)
    response.raise_for_status()

    return list(map(lambda ld: PhysicalDevice.parse_obj(ld), response.json()))


def get_physical_notes(uid: str, token: str) -> List[dict]:
    """
        Get all notes from a physical device

        Params:
            uid: str - uid of physical device
            token: str - authentication token of user
    """
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(f"{end_point}/broker/api/physical/devices/notes/{uid}", headers=headers)

    response.raise_for_status()
    return list(map(lambda note: DeviceNote.parse_obj(note), response.json()))


def get_logical_devices(token: str, include_properties: bool = False):
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(
        f'{end_point}/broker/api/logical/devices/?include_properties={include_properties}', headers=headers)
    response.raise_for_status()

    return list(map(lambda ld: LogicalDevice.parse_obj(ld), response.json()))


def get_physical_unmapped(token: str):
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(f'{end_point}/broker/api/physical/devices/unmapped/',
                            headers=headers)
    response.raise_for_status()
    return response.json()


def get_physical_device(uid: str, token: str) -> dict:
    """
        Get a physical device object from a uid

        Params:
            uid: str - uid of physical device
            token: str - user's authentication token

        returns:
            physical_device: dict - Phyical device object
    """

    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(f'{end_point}/broker/api/physical/devices/{uid}',headers=headers)
    response.raise_for_status()

    return response.json()


def get_logical_device(uid: str, token: str) -> dict:
    """
        Get a logical device object from a uid

        Params:
            uid: str - uid of logical device
            token: str - user's authentication token

        returns:
            logical_device: dict - Logical device object
    """

    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(f'{end_point}/broker/api/logical/devices/{uid}',
                            headers=headers)
    response.raise_for_status()
    return response.json()


def get_current_mappings(token: str):
    """
        Returns the current mapping for all physical devices. A current mapping is one with no end time set, meaning messages from the physical device will be forwarded to the logical device.
    """
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(f"{end_point}/broker/api/mappings/current/", headers=headers)
    response.raise_for_status()

    return list(map(lambda mapping_obj: PhysicalToLogicalMapping.parse_obj(mapping_obj), response.json()))


def get_all_mappings_for_logical_device(uid: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(f'{end_point}/broker/api/mappings/logical/all/{uid}', headers=headers)
    response.raise_for_status()
    return list(map(lambda ld: PhysicalToLogicalMapping.parse_obj(ld), response.json()))


def get_current_mapping_from_physical_device(uid: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(f'{end_point}/broker/api/mappings/physical/current/{uid}', headers=headers)

    if response.status_code == 404:
        return

    response.raise_for_status()
    return list(map(lambda mapping_obj: PhysicalToLogicalMapping.parse_obj(mapping_obj), response.json()))


def get_all_mappings_for_physical_device(uid:str, token:str):
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(f'{end_point}/broker/api/mappings/physical/all/{uid}', headers=headers)

    if response.status_code == 404:
        return

    response.raise_for_status()
    return list(map(lambda mapping_obj: PhysicalToLogicalMapping.parse_obj(mapping_obj), response.json()))


def update_physical_device(uid: str, name: str, location: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    device = get_physical_device(uid, token)
    device['name'] = name
    device['location'] = location
    response = requests.patch(f'{end_point}/broker/api/physical/devices/', headers=headers, json=device)
    response.raise_for_status()
    return response.json()


def update_logical_device(uid: str, name: str, location: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    device = get_logical_device(uid, token)
    device['name'] = name
    device['location'] = location
    response = requests.patch(
        f'{end_point}/broker/api/logical/devices/', headers=headers, json=device)
    response.raise_for_status()

    return response.json()


def end_logical_mapping(uid: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    url = f'{end_point}/broker/api/mappings/logical/end/{uid}'
    requests.patch(url, headers=headers)


def end_physical_mapping(uid: str, token: str):
    """
        End device mapping from a physical device (if any). If there was a mapping, the logical device also has no mapping after this call.

        Params:
            uid: str - end mapping on the physical device with this uid
            token:str - user's authentication token
    """
    headers = {"Authorization": f"Bearer {token}"}

    url = f'{end_point}/broker/api/mappings/physical/end/{uid}'
    response = requests.patch(url, headers=headers)

    # 404 is returned when there are no device mappings
    if response.status_code != 200 and response.status_code != 404:
        response.raise_for_status()

def toggle_device_mapping(uid:str, dev_type:str, is_active:bool, token:str):
    """
        Send request to restAPI to toggle the status of the device mapping
    """

    headers = {"Authorization": f"Bearer {token}"}

    url = f'{end_point}/broker/api/mappings/toggle-active/'
    body={
        'luid':uid if dev_type == 'LD' else None,
        'puid': uid if dev_type == 'PD' else None,
        'is_active':is_active
    }

    response = requests.patch(url, headers=headers, params=body)

    # 404 is returned when there are no device mappings
    if response.status_code != 200:
        response.raise_for_status()

def create_logical_device(physical_device: dict, token: str) ->str:
    """
        Create a logical device from physical device

        Params:
            physical_device: JSON - Physical device info to be compited
            token: str - Users authentication token

        returns:
            uid: str - uid of newly created logical device
    """

    headers = {"Authorization": f"Bearer {token}"}

    timeObject = datetime.now()
    logicalJson = {
        "uid": 0,
        "name": physical_device['name'],
        "location": physical_device['location'],
        "last_seen": str(timeObject),
        "properties": physical_device['properties']
    }
    response = requests.post(
        f'{end_point}/broker/api/logical/devices/', json=logicalJson, headers=headers)
    response.raise_for_status()

    logical_device = response.json()
    return logical_device['uid']


def delete_note(uid: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    baseUrl = f'{end_point}/broker/api/physical/devices/notes/{uid}'
    response = requests.delete(baseUrl, headers=headers)
    response.raise_for_status()

    return response.json()


def insert_device_mapping(physicalUid: str, logicalUid: str, token: str):

    """
        Create a device mapping between a physical and logical device

        Params:
            physicalUid: str - uid of physical device
            logicalUid: str - uid of logical device

        returns:

    """
    headers = {"Authorization": f"Bearer {token}"}

    logicalDevice = get_logical_device(logicalUid, token=token)
    physicalDevice = get_physical_device(physicalUid, token=token)
    timeObject = datetime.now()
    end_physical_mapping(physicalUid, token=token)

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
    response = requests.post(f'{end_point}/broker/api/mappings/', json=mappingJson, headers=headers)
    response.raise_for_status()

    return response.json()


def insert_note(noteText: str, uid: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    noteJson = {
        "note": noteText
    }
    baseUrl = f'{end_point}/broker/api/physical/devices/notes/{uid}'
    response = requests.post(baseUrl, json=noteJson,
                             headers=headers)
    response.raise_for_status()

    return response.json()


def edit_note(noteText: str, uid: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    timeObject = datetime.now()
    noteJson = {
        "uid": int(uid),
        "ts": str(timeObject),
        "note": str(noteText)
    }
    baseUrl = f'{end_point}/broker/api/physical/devices/notes/'
    response = requests.patch(baseUrl, json=noteJson,
                              headers=headers)
    response.raise_for_status()
    return response.json()


def format_json(data) -> str:
    return (json.dumps(data, indent=4, sort_keys=True))


def get_user_token(username: str, password: str) -> str:
    """
        Get users authentiation token, provided username and password are correct

        Params:
            username: str - the user's username
            password: str - the user's password

        returns:
            token: str - User's authentication token

    """
    headers = {
        "Authorization": f"Basic {base64.b64encode(f'{username}:{password}'.encode()).decode()}"}

    response = requests.get(f"{end_point}/broker/api/token", headers=headers)
    response.raise_for_status()

    return response.json()


def change_user_password(password: str, token: str) -> str:
    """
        Change users password

        Params:
            password: str - User's new password
            token: str - User's authentication token
        
        reutrn:
            token: str - User's new authentication token
    """
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(f"{end_point}/broker/api/change-password", headers=headers, params={"password":password})
    response.raise_for_status()

    return response.json()
