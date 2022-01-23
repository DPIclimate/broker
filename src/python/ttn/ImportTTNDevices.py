import requests
#import sys

import TTNAPI as ttn
from ..pdmodels.Models import PhysicalDevice, Location


_BASE = "http://restapi:5687/api/physical"
_HEADERS = {
    "Content-Type": "application/json"
}


def main():
    print(sys.path)
    return

    apps = ttn.get_applications()
    for a in apps['applications']:
        #print(a)
        app_id = a['ids']['application_id']
        if app_id == 'oai-test-devices' or app_id == 'ndvi-dpi-hemistop' or app_id == 'ndvisoil-dpi-stop5tm':
            print(f'skipping {app_id}')
            continue

        print(app_id)
        devs = ttn.get_devices(app_id)
        #print(devs)
        if 'end_devices' not in devs:
            continue

        for d in devs['end_devices']:
            dev_id = d['ids']['device_id']
            #dev_eui = d['ids']['dev_eui'] if 'dev_eui' in d['ids'] else 'NO DEV_EUI'
            dev_name = d['name'] if 'name' in d else dev_id
            dev_loc = None

            if 'locations' in d and 'user' in d['locations']:
                user_loc = d['locations']['user']
                dev_lat = user_loc['latitude']
                dev_long = user_loc['longitude']
                dev_loc = Location(lat=dev_lat, long=dev_long)

            props = {}
            props["app_id"] = app_id
            props["dev_id"] = dev_id

            pd = PhysicalDevice(source_name='ttn', name=dev_name, location=dev_loc, properties=props)

            url=f"{_BASE}/devices/?prop_name=app_id&prop_value={app_id}&prop_name=dev_id&prop_value={dev_id}"
            r = requests.get(url, headers=_HEADERS)
            if r.status_code == 200:
                print(r.json())
                existing_dev = PhysicalDevice.parse_obj(r.json()[0])
                print(f'Device exists: {existing_dev}')
            else:
                print('Adding device to broker')
                url=f"{_BASE}/devices/"
                payload = pd.json()
                r = requests.post(url, headers=_HEADERS, data=payload)
                print(r.status_code, r.reason, r.text)

    #print(dev_tups)
    #db.create_physical_device(dev_tups)

if __name__ == "__main__":
    main()
