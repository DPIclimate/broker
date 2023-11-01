import json
from typing import List
import sys
from typing import List
import requests
from datetime import datetime, timezone
import base64

from pdmodels.Models import PhysicalDevice, LogicalDevice, PhysicalToLogicalMapping, DeviceNote, Location


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

    response = requests.get(f'{end_point}/broker/api/physical/devices/unmapped/', headers=headers)
    response.raise_for_status()
    return response.json()


def get_physical_device(uid: str, token: str) -> PhysicalDevice:
    """
        Get a physical device object from a uid

        Params:
            uid: str - uid of physical device
            token: str - user's authentication token

        returns:
            physical_device: dict - Phyical device object
    """
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f'{end_point}/broker/api/physical/devices/{uid}', headers=headers)
    response.raise_for_status()
    return PhysicalDevice.parse_obj(response.json())


def get_logical_device(uid: str, token: str) -> LogicalDevice:
    """
        Get a logical device object from a uid

        Params:
            uid: str - uid of logical device
            token: str - user's authentication token

        returns:
            logical_device: dict - Logical device object
    """

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f'{end_point}/broker/api/logical/devices/{uid}', headers=headers)
    response.raise_for_status()
    return LogicalDevice.parse_obj(response.json())


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


def update_physical_device(uid: int, name: str, location: Location | None, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    device: PhysicalDevice = get_physical_device(uid, token)
    device.name = name
    device.location = location
    response = requests.patch(f'{end_point}/broker/api/physical/devices/', headers=headers, data=device.json())
    response.raise_for_status()
    return PhysicalDevice.parse_obj(response.json())


def update_logical_device(uid: int, name: str, location: Location | None, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    device = get_logical_device(uid, token)
    device.name = name
    device.location = location
    response = requests.patch(f'{end_point}/broker/api/logical/devices/', headers=headers, data=device.json())
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


def toggle_device_mapping(uid: int, dev_type: str, is_active: bool, token: str):
    """
        Send request to restAPI to toggle the status of the device mapping
    """

    headers = {"Authorization": f"Bearer {token}"}

    url = f'{end_point}/broker/api/mappings/toggle-active/'
    body = {
        'is_active': is_active
    }

    if dev_type == 'LD':
        body['luid'] = uid
    elif dev_type == 'PD':
        body['puid'] = uid
    else:
        raise RuntimeError(f'Invalid dev_type: {dev_type}')

    response = requests.patch(url, headers=headers, params=body)

    # 404 is returned when there are no device mappings
    if response.status_code != 200:
        response.raise_for_status()


def create_logical_device(physical_device: PhysicalDevice, token: str) ->str:
    """
        Create a logical device from physical device

        Params:
            physical_device: JSON - Physical device info to be compited
            token: str - Users authentication token

        returns:
            uid: str - uid of newly created logical device
    """

    headers = {"Authorization": f"Bearer {token}"}

    logicalJson = {
        "uid": 0,
        "name": physical_device.name,
        "location": physical_device.location,
    }

    response = requests.post(f'{end_point}/broker/api/logical/devices/', json=logicalJson, headers=headers)
    response.raise_for_status()

    logical_device = response.json()
    return logical_device['uid']


def delete_note(uid: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    baseUrl = f'{end_point}/broker/api/physical/devices/notes/{uid}'
    response = requests.delete(baseUrl, headers=headers)
    response.raise_for_status()

    return response.json()


def insert_device_mapping(p_uid: int, l_uid: int, token: str):
    """
        Create a device mapping between a physical and logical device

        Params:
            physicalUid: int - uid of physical device
            logicalUid: int - uid of logical device
            token: str - bearer token for the current session
        returns:

    """
    headers = {"Authorization": f"Bearer {token}"}

    l_dev: LogicalDevice = get_logical_device(l_uid, token=token)
    p_dev: PhysicalDevice = get_physical_device(p_uid, token=token)
    now = datetime.now(tz=timezone.utc)
    end_physical_mapping(p_uid, token=token)

    mapping = PhysicalToLogicalMapping(pd=p_dev, ld=l_dev, start_time=now)

    response = requests.post(f'{end_point}/broker/api/mappings/', data=mapping.json(), headers=headers)
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

def get_puid_ts(puid: str):
    try:
        response = requests.get(f"{end_point}/query/?query=select timestamp,name,value from timeseries where p_uid={puid} and timestamp >= current_date - interval '30 days' order by timestamp asc")
        response.raise_for_status()
        #print("get_puid_ts ---returns---", file=sys.stderr)
        #print(response.json(), file=sys.stderr)
        return response.json()
    except Exception as err:
        print(f"webapp: unable to pull ts_luid data from api: {err}")
        return {}


def get_luid_ts(luid: str):
    try:
        response = requests.get(f"{end_point}/query/?query=select timestamp,name,value from timeseries where l_uid={luid} and timestamp >= current_date - interval '30 days' order by timestamp asc")
        response.raise_for_status()
        #print("get_puid_ts ---returns---", file=sys.stderr)
        #print(response.json(), file=sys.stderr)
        return response.json()
    except Exception as err:
        print(f"webapp: unable to pull ts_luid data from api: {err}")
        return {}


def get_between_dates_ts(dev_type: str, uid: str, from_date: str, to_date: str):
    try:
        response = requests.get(f"{end_point}/query/?query=select p_uid, l_uid, timestamp, name, value from timeseries where {dev_type}='{uid}' and timestamp BETWEEN '{from_date} 00:00:00' AND '{to_date} 23:59:59' order by timestamp asc")
        response.raise_for_status()
        #print("get_between dates ---returns---", file=sys.stderr)
        #print(response.json(), file=sys.stderr)
        return response.json()
    except Exception as err:
        print(f"webapp: unable to pull get_between_dates_ts data from api: {err}")
        return {}
