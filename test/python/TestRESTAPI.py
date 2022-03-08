import copy, datetime, logging, time, unittest, uuid
from typing import Tuple

import api.client.DAO as dao
import requests

from pdmodels.Models import DeviceNote, PhysicalDevice, PhysicalToLogicalMapping, Location, LogicalDevice
from typing import Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
logger = logging.getLogger(__name__)

_BASE = "http://restapi:5687/api"
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

class TestRESTAPI(unittest.TestCase):

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

    def test_create_device_note(self):
        dev, new_dev = self._create_default_physical_device()

        note1 = DeviceNote(note="Note1")
        url=f'{_BASE}/physical/devices/notes/{new_dev.uid}'
        r = requests.post(url, headers=_HEADERS, data=note1.json())
        self.assertEqual(r.status_code, 201)

        url=f'{_BASE}/physical/devices/notes/{-1}'
        r = requests.post(url, headers=_HEADERS, data=note1.json())
        self.assertEqual(r.status_code, 404)

    def test_get_device_notes(self):
        dev, new_dev = self._create_default_physical_device()

        note1 = DeviceNote(note="Note1")
        note2 = DeviceNote(note="Note2")
        note3 = DeviceNote(note="Note3")

        url=f'{_BASE}/physical/devices/notes/{new_dev.uid}'
        r = requests.post(url, headers=_HEADERS, data=note1.json())
        self.assertEqual(r.status_code, 201)

        time.sleep(0.01)
        r = requests.post(url, headers=_HEADERS, data=note2.json())
        self.assertEqual(r.status_code, 201)

        time.sleep(0.01)
        r = requests.post(url, headers=_HEADERS, data=note3.json())
        self.assertEqual(r.status_code, 201)

        # Confirm multiple notes are returned in ascending timestamp order.
        r = requests.get(url)
        self.assertEqual(r.status_code, 200)
        notes = [DeviceNote.parse_obj(n) for n in r.json()]
        self.assertIsNotNone(notes)
        self.assertEqual(len(notes), 3)
        self.assertLess(notes[0].ts, notes[1].ts)
        self.assertLess(notes[1].ts, notes[2].ts)

        # Confirm an empty array is returned for an invalid device id.
        url=f'{_BASE}/physical/devices/notes/{-1}'
        r = requests.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 0)

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

    def test_get_mapping_from_physical(self):
        pdev, new_pdev = self._create_default_physical_device()
        ldev, new_ldev = self._create_default_logical_device()
        mapping = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=self.now())

        url=f'{_BASE}/mappings/'
        payload = mapping.json()
        r = requests.post(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 201)

        # Confirm getting the mapping works.
        r = requests.get(f'{_BASE}/mappings/from_physical/{new_pdev.uid}')
        self.assertEqual(r.status_code, 200)
        m = PhysicalToLogicalMapping.parse_obj(r.json())
        self.assertEqual(mapping, m)

        # Confirm getting an invalid map returns 404
        r = requests.get(f'{_BASE}/mappings/from_physical/{-1}')
        self.assertEqual(r.status_code, 404)

        # Confirm the latest mapping is returned.
        time.sleep(0.001)
        mapping2 = copy.deepcopy(mapping)
        mapping2.start_time=self.now()
        self.assertNotEqual(mapping, mapping2)
        payload = mapping2.json()
        r = requests.post(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 201)

        r = requests.get(f'{_BASE}/mappings/from_physical/{new_pdev.uid}')
        self.assertEqual(r.status_code, 200)
        m = PhysicalToLogicalMapping.parse_obj(r.json())
        self.assertEqual(mapping2, m)

    def test_get_mapping_from_logical(self):
        pdev, new_pdev = self._create_default_physical_device()
        ldev, new_ldev = self._create_default_logical_device()
        mapping = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=self.now())

        url=f'{_BASE}/mappings/'
        payload = mapping.json()
        r = requests.post(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 201)

        # Confirm getting the mapping works.
        r = requests.get(f'{_BASE}/mappings/from_logical/{new_ldev.uid}')
        self.assertEqual(r.status_code, 200)
        m = PhysicalToLogicalMapping.parse_obj(r.json())
        self.assertEqual(mapping, m)

        # Confirm getting an invalid map returns 404
        r = requests.get(f'{_BASE}/mappings/from_logical/{-1}')
        self.assertEqual(r.status_code, 404)

        # Confirm the latest mapping is returned.
        time.sleep(0.001)
        mapping2 = copy.deepcopy(mapping)
        mapping2.start_time=self.now()
        self.assertNotEqual(mapping, mapping2)
        payload = mapping2.json()
        r = requests.post(url, headers=_HEADERS, data=payload)
        self.assertEqual(r.status_code, 201)

        r = requests.get(f'{_BASE}/mappings/from_logical/{new_ldev.uid}')
        self.assertEqual(r.status_code, 200)
        m = PhysicalToLogicalMapping.parse_obj(r.json())
        self.assertEqual(mapping2, m)
