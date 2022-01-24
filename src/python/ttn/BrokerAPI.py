import requests

from pdmodels.Models import PhysicalDevice

_BASE = "http://restapi:5687/api/physical"
_HEADERS = {
    "Content-Type": "application/json"
}

class BrokerAPIException(BaseException):
    pass


def get_physical_device(app_id: str, dev_id: str) -> PhysicalDevice:
    url=f"{_BASE}/devices/?prop_name=app_id&prop_value={app_id}&prop_name=dev_id&prop_value={dev_id}"
    r = requests.get(url, headers=_HEADERS)
    if r.status_code == 200:
        # This REST call always returns an array of devices, which may be empty if no devices
        # match the query.
        dev_array = r.json()
        if len(dev_array) == 1:
            dev = PhysicalDevice.parse_obj(r.json()[0])
            return dev

    raise BrokerAPIException('No such device.')


def create_physical_device(dev: PhysicalDevice) -> PhysicalDevice:
    url=f"{_BASE}/devices/"
    payload = dev.json()
    r = requests.post(url, headers=_HEADERS, data=payload)
    if r.status_code == 201:
        new_dev = PhysicalDevice.parse_obj(r.json())
        return new_dev

    raise BrokerAPIException(f'Create physical device failed: {r.status_code}: {r.reason}')
