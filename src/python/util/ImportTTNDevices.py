#
# TODO:
#
# Consider the ability to update a device on TTN based upon broker information, or the
# other way around. Where is the source of truth?
#

import api.client.TTNAPI as ttn
import db.DAO as dao

from pdmodels.Models import PhysicalDevice, Location


#
# This import does not need to run periodically because once the broker is running it creates
# new physical devices itself.
#

def main():
    apps = ttn.get_applications()
    for a in apps['applications']:
        #print(a)
        app_id = a['ids']['application_id']
        
        # Skip devices that seem to be dead.
        if app_id == 'ndvi-dpi-hemistop' or app_id == 'ndvisoil-dpi-stop5tm':
            print(f'skipping {app_id}')
            continue

        print(app_id)
        devs = ttn.get_devices(app_id)
        #print(devs)
        if 'end_devices' not in devs:
            continue

        for d in devs['end_devices']:
            dev_id = d['ids']['device_id']

            # Only allow this one test device in for now.
            if app_id == 'oai-test-devices' and dev_id != 'atmega328-v1':
                print(f'skipping {app_id}')
                continue

            dev_eui = d['ids']['dev_eui'].lower() if 'dev_eui' in d['ids'] else 'NO DEV_EUI'
            dev_name = d['name'] if 'name' in d else dev_id
            dev_loc = None

            if 'locations' in d and 'user' in d['locations']:
                user_loc = d['locations']['user']
                dev_lat = user_loc['latitude']
                dev_long = user_loc['longitude']
                dev_loc = Location(lat=dev_lat, long=dev_long)

            props = {}
            props['app_id'] = app_id
            props['dev_id'] = dev_id

            # Need the dev_eui for the initial matching to ubidots devices.
            props['dev_eui'] = dev_eui

            pd = PhysicalDevice(source_name='ttn', name=dev_name, location=dev_loc, properties=props)

            existing_dev_list = dao.get_physical_devices(query_args={'prop_name': ['app_id', 'dev_id'], 'prop_value': [app_id, dev_id]})
            if len(existing_dev_list) > 0:
                print(f'Device exists: {existing_dev_list[0]}')
            else:
                print('Adding device to broker')
                dao.create_physical_device(pd)


if __name__ == "__main__":
    main()
