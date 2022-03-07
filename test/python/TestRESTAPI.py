import copy, datetime, logging, time, unittest, uuid
from typing import Tuple

import api.client.DAO as dao
import requests

from pdmodels.Models import PhysicalDevice, PhysicalToLogicalMapping, Location, LogicalDevice
from typing import Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
logger = logging.getLogger(__name__)

_BASE = "http://restapi:5687/api"
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

class TestDAO(unittest.TestCase):

    def setUp(self):
        try:
            with dao._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''truncate physical_logical_map;
                    truncate physical_devices cascade;
                    truncate logical_devices cascade;
                    truncate physical_logical_map cascade;
                    truncate device_notes cascade;
                    truncate raw_messages cascade''')
        finally:
            dao.free_conn(conn)

    def now(self):
        return datetime.datetime.now(tz=datetime.timezone.utc)

    def _create_default_physical_device(self, dev=None) -> Tuple[PhysicalDevice, PhysicalDevice]:
        if dev is None:
            last_seen = self.now()
            dev = PhysicalDevice(source_name='ttn', name='Test Device', location=Location(lat=3, long=-31), last_seen=last_seen,
                source_ids={'appId': 'x', 'devId': 'y'},
                properties={'appId': 'x', 'devId': 'y', 'other': 'z'})

        url=f'{_BASE}/physical/devices/'
        payload = dev.json()
        r = requests.post(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 201)
        new_dev = PhysicalDevice.parse_obj(r.json())
        self.assertEqual(r.headers['Location'], f'{url}{new_dev.uid}')
        return (dev, new_dev)

    def test_get_all_physical_sources(self):
        url=f'{_BASE}/physical/sources/'
        r = requests.get(url, headers=_HEADERS)
        self.assertEqual(r.status_code, 200)
        sources = r.json()
        self.assertEqual(sources, ['greenbrain', 'ttn'])

    def test_create_physical_device(self):
        dev, new_dev = self._create_default_physical_device()

        # Don't fail the equality assertion due to the uid being None in dev.
        dev.uid = new_dev.uid
        self.assertEqual(dev, new_dev)

    def test_get_physical_device(self):
        url=f'{_BASE}/physical/devices/1'
        r = requests.get(url, headers=_HEADERS)
        self.assertEqual(r.status_code, 404)

        dev, new_dev = self._create_default_physical_device()

        url=f'{_BASE}/physical/devices/{new_dev.uid}'
        r = requests.get(url, headers=_HEADERS)
        self.assertEqual(r.status_code, 200)
        got_dev = PhysicalDevice.parse_obj(r.json())
        self.assertEqual(new_dev, got_dev)

    def test_get_physical_devices_using_source_ids(self):
        dev, new_dev = self._create_default_physical_device()

        url=f'{_BASE}/physical/devices/'
        params = {'source': 'ttn', 'source_id_name': 'appId', 'source_id_value': 'x'}
        r = requests.get(url, headers=_HEADERS, params=params)
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertIsNotNone(j)
        self.assertEqual(len(j), 1)

        # Note the devs must be parsed by the PhysicalDevice class to convert
        # the ISO-8601 strings into datetime objects or the comparsion will not
        # work.
        parsed_devs = [PhysicalDevice.parse_obj(d) for d in j]
        self.assertEqual(new_dev, parsed_devs[0])

        # Check we get two devices back from a shared source id value.
        dev.last_seen = self.now()
        dev.source_ids['devId'] = 'z'
        dev, new_dev2 = self._create_default_physical_device(dev)

        params = {'source': 'ttn', 'source_id_name': 'appId', 'source_id_value': 'x'}
        r = requests.get(url, headers=_HEADERS, params=params)
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertIsNotNone(j)
        self.assertEqual(len(j), 2)

        # Note the devs must be parsed by the PhysicalDevice class to convert
        # the ISO-8601 strings into datetime objects or the comparsion will not
        # work.
        parsed_devs = [PhysicalDevice.parse_obj(d) for d in j]
        self.assertEqual(new_dev, parsed_devs[0])
        self.assertEqual(new_dev2, parsed_devs[1])

        params = {'source': 'ttn', 'source_id_name': 'appId,devId', 'source_id_value': 'x,z'}
        r = requests.get(url, headers=_HEADERS, params=params)
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertIsNotNone(j)
        self.assertEqual(len(j), 1)

        # Note the devs must be parsed by the PhysicalDevice class to convert
        # the ISO-8601 strings into datetime objects or the comparsion will not
        # work.
        parsed_devs = [PhysicalDevice.parse_obj(d) for d in j]
        self.assertEqual(new_dev2, parsed_devs[0])

        # Confirm no results comes back as an empty list.
        params = {'source': 'INVALID', 'source_id_name': 'appId', 'source_id_value': 'x'}
        r = requests.get(url, headers=_HEADERS, params=params)
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertIsNotNone(j)
        self.assertEqual(len(j), 0)

    def test_update_physical_device(self):
        dev, new_dev = self._create_default_physical_device()

        # Confirm no update works.
        url=f"{_BASE}/physical/devices/"
        payload = new_dev.json()
        r = requests.patch(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 200)
        updated_dev = PhysicalDevice.parse_obj(r.json())
        self.assertEqual(updated_dev, new_dev)

        new_dev.name = 'X'
        payload = new_dev.json()
        r = requests.patch(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 200)
        updated_dev = PhysicalDevice.parse_obj(r.json())
        self.assertEqual(updated_dev, new_dev)

        new_dev.properties['q1'] = {'q2': 22}
        payload = new_dev.json()
        r = requests.patch(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 200)
        updated_dev = PhysicalDevice.parse_obj(r.json())
        self.assertEqual(updated_dev, new_dev)

        # Confirm a DAOException is raised if an invalid uid is given to update.
        new_dev.uid = -1
        payload = dev.json()
        r = requests.patch(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 404)

    def test_delete_physical_device(self):
        dev, new_dev = self._create_default_physical_device()

        url=f'{_BASE}/physical/devices/{new_dev.uid}'
        r = requests.delete(url, headers=_HEADERS)
        self.assertEqual(r.status_code, 200)
        deleted_dev = PhysicalDevice.parse_obj(r.json())

        self.assertEqual(deleted_dev, new_dev)

        # Confirm the device was deleted.
        r = requests.get(url, headers=_HEADERS)
        self.assertEqual(r.status_code, 404)

        # Confirm delete does not throw an exception when the device does not exist.
        r = requests.delete(url, headers=_HEADERS)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json())

    """--------------------------------------------------------------------------
    LOGICAL DEVICES
    --------------------------------------------------------------------------"""

    def _create_default_logical_device(self, dev=None) -> Tuple[LogicalDevice, LogicalDevice]:
        if dev is None:
            last_seen = self.now()
            dev = LogicalDevice(name='Test Device', location=Location(lat=3, long=-31), last_seen=last_seen,
                properties={'appId': 'x', 'devId': 'y', 'other': 'z'})

        url=f'{_BASE}/logical/devices/'
        payload = dev.json()
        r = requests.post(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 201)
        new_dev = LogicalDevice.parse_obj(r.json())
        self.assertEqual(r.headers['Location'], f'{url}{new_dev.uid}')
        return (dev, new_dev)

    def test_create_logical_device(self):
        dev, new_dev = self._create_default_logical_device()

        # Don't fail the equality assertion due to the uid being None in dev.
        dev.uid = new_dev.uid
        self.assertEqual(dev, new_dev)


    def test_get_logical_device(self):
        url=f'{_BASE}/logical/devices/1'
        r = requests.get(url, headers=_HEADERS)
        self.assertEqual(r.status_code, 404)

        dev, new_dev = self._create_default_logical_device()

        url=f'{_BASE}/logical/devices/{new_dev.uid}'
        r = requests.get(url, headers=_HEADERS)
        self.assertEqual(r.status_code, 200)
        got_dev = LogicalDevice.parse_obj(r.json())
        self.assertEqual(new_dev, got_dev)


    def test_update_logical_device(self):
        dev, new_dev = self._create_default_logical_device()

        # Confirm no update works.
        url=f"{_BASE}/logical/devices/"
        payload = new_dev.json()
        r = requests.patch(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 200)
        updated_dev = LogicalDevice.parse_obj(r.json())
        self.assertEqual(updated_dev, new_dev)

        new_dev.name = 'X'
        payload = new_dev.json()
        r = requests.patch(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 200)
        updated_dev = LogicalDevice.parse_obj(r.json())
        self.assertEqual(updated_dev, new_dev)

        new_dev.properties['q1'] = {'q2': 22}
        payload = new_dev.json()
        r = requests.patch(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 200)
        updated_dev = LogicalDevice.parse_obj(r.json())
        self.assertEqual(updated_dev, new_dev)

        # Confirm a DAOException is raised if an invalid uid is given to update.
        new_dev.uid = -1
        payload = dev.json()
        r = requests.patch(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 404)

    def test_delete_logical_device(self):
        dev, new_dev = self._create_default_logical_device()

        url=f'{_BASE}/logical/devices/{new_dev.uid}'
        r = requests.delete(url, headers=_HEADERS)
        self.assertEqual(r.status_code, 200)
        deleted_dev = LogicalDevice.parse_obj(r.json())

        self.assertEqual(deleted_dev, new_dev)

        # Confirm the device was deleted.
        r = requests.get(url, headers=_HEADERS)
        self.assertEqual(r.status_code, 404)

        # Confirm delete does not throw an exception when the device does not exist.
        r = requests.delete(url, headers=_HEADERS)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json())

    def test_insert_mapping(self):
        pdev, new_pdev = self._create_default_physical_device()
        ldev, new_ldev = self._create_default_logical_device()
        mapping = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=self.now())

        # This should work.
        url=f'{_BASE}/mappings/'
        payload = mapping.json()
        r = requests.post(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 201)

        # This should fail due to duplicate start time.
        r = requests.post(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 400)

        time.sleep(0.001)
        mapping.start_time=self.now()
        payload = mapping.json()
        r = requests.post(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 201)

        pdx = copy.deepcopy(new_pdev)
        pdx.uid = -1
        mapping = PhysicalToLogicalMapping(pd=pdx, ld=new_ldev, start_time=self.now())
        # This should fail due to invalid physical uid.
        payload = mapping.json()
        r = requests.post(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 404)

        ldx = copy.deepcopy(new_ldev)
        ldx.uid = -1
        mapping = PhysicalToLogicalMapping(pd=new_pdev, ld=ldx, start_time=self.now())
        # This should fail due to invalid logical uid.
        payload = mapping.json()
        r = requests.post(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 404)
