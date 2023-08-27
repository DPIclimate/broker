import base64
import copy, datetime, logging, time, unittest, uuid
from typing_extensions import assert_type
import re
from typing import Tuple

import api.client.DAO as dao
import requests

from pdmodels.Models import DeviceNote, PhysicalDevice, PhysicalToLogicalMapping, Location, LogicalDevice
from typing import Tuple

import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
logger = logging.getLogger(__name__)

_BASE = "http://restapi:5687/broker/api"


class TestRESTAPI(unittest.TestCase):
    _username = ""
    _token = ""
    _admin_username = ""
    _admin_token = ""

    _HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": ""
    }

    _ADMIN_HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": ""
    }

    def setUp(self):

        try:
            with dao._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''truncate physical_logical_map;
                    truncate physical_devices cascade;
                    truncate logical_devices cascade;
                    truncate physical_logical_map cascade;
                    truncate device_notes cascade;
                    truncate raw_messages cascade;
                    truncate users;''')
        finally:
            dao.free_conn(conn)

        # Create a non-admin user and make a valid token so the APIs don't return 401.
        self._username = self._create_test_user()
        self._token = dao.user_get_token(self._username, 'password')
        self._HEADERS['Authorization'] = f'Bearer {self._token}'

        # Create an admin user for use with any requests that don't use a 'GET' request.
        self._admin_username = self._create_test_user()
        dao.user_set_read_only(self._admin_username, False)
        self._admin_token = dao.user_get_token(self._admin_username, 'password')
        self._ADMIN_HEADERS['Authorization'] = f'Bearer {self._admin_token}'

    def now(self):
        return datetime.datetime.now(tz=datetime.timezone.utc)

    def _create_physical_device(self, expected_code=201, req_header=_HEADERS, dev=None) -> Tuple[
        PhysicalDevice, PhysicalDevice]:
        if dev is None:
            last_seen = self.now()
            dev = PhysicalDevice(source_name='ttn', name='Test Device', location=Location(lat=3, long=-31),
                                 last_seen=last_seen,
                                 source_ids={'appId': 'x', 'devId': 'y'},
                                 properties={'appId': 'x', 'devId': 'y', 'other': 'z'})

        url = f'{_BASE}/physical/devices/'
        payload = dev.json()
        r = requests.post(url, headers=req_header, data=payload)
        self.assertEqual(r.status_code, expected_code)

        new_dev = None

        if expected_code == 201:
            new_dev = PhysicalDevice.parse_obj(r.json())
            self.assertEqual(r.headers['Location'], f'{url}{new_dev.uid}')
        return (dev, new_dev)

    def _create_test_user(self) -> str:
        test_uname = os.urandom(4).hex()
        dao.user_add(uname=test_uname, passwd='password', disabled=False)
        return test_uname

    def test_get_all_physical_sources(self):
        url = f'{_BASE}/physical/sources/'
        r = requests.get(url, headers=self._HEADERS)
        self.assertEqual(r.status_code, 200)
        sources = r.json()
        self.assertEqual(sources, ['greenbrain', 'ict_eagleio', 'ttn', 'wombat', 'ydoc'])

        self._HEADERS['Authorization'] = ""
        r = requests.get(url, headers=self._HEADERS)
        self.assertEqual(r.status_code, 401)

        self._HEADERS.pop('Authorization')
        r = requests.get(url, headers=self._HEADERS)
        self.assertEqual(r.status_code, 401)

    def test_create_physical_device(self):
        dev, new_dev = self._create_physical_device(expected_code=403, req_header=self._HEADERS)

        dev, new_dev = self._create_physical_device(req_header=self._ADMIN_HEADERS)

        # Don't fail the equality assertion due to the uid being None in dev.
        dev.uid = new_dev.uid
        self.assertEqual(dev, new_dev)

    def test_get_physical_device(self):
        url = f'{_BASE}/physical/devices/1'
        r = requests.get(url, headers=self._HEADERS)
        self.assertEqual(r.status_code, 404)  # 404 device not found, shouldn't exist.

        dev, new_dev = self._create_physical_device(req_header=self._ADMIN_HEADERS)

        url = f'{_BASE}/physical/devices/{new_dev.uid}'
        r = requests.get(url, headers=self._HEADERS)
        self.assertEqual(r.status_code, 200)
        got_dev = PhysicalDevice.parse_obj(r.json())
        self.assertEqual(new_dev, got_dev)

    def test_get_physical_devices_using_source_names(self):
        dev, new_dev = self._create_physical_device(req_header=self._ADMIN_HEADERS)

        url = f'{_BASE}/physical/devices/'
        params = {'source_name': 'ttn'}
        r = requests.get(url, headers=self._HEADERS, params=params)
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertIsNotNone(j)
        self.assertEqual(len(j), 1)

        # Note the devs must be parsed by the PhysicalDevice class to convert
        # the ISO-8601 strings into datetime objects or the comparsion will not
        # work.
        parsed_devs = [PhysicalDevice.parse_obj(d) for d in j]
        self.assertEqual(new_dev, parsed_devs[0])

        params = {'source_name': 'ydoc'}
        r = requests.get(url, headers=self._HEADERS, params=params)
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertIsNotNone(j)
        self.assertEqual(len(j), 0)

    def test_update_physical_device(self):
        dev, new_dev = self._create_physical_device(req_header=self._ADMIN_HEADERS)

        # Confirm no update works.
        url = f"{_BASE}/physical/devices/"
        payload = new_dev.json()
        r = requests.patch(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 200)
        updated_dev = PhysicalDevice.parse_obj(r.json())
        self.assertEqual(updated_dev, new_dev)

        new_dev.name = 'X'
        payload = new_dev.json()
        r = requests.patch(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 200)
        updated_dev = PhysicalDevice.parse_obj(r.json())
        self.assertEqual(updated_dev, new_dev)

        new_dev.properties['q1'] = {'q2': 22}
        payload = new_dev.json()
        r = requests.patch(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 200)
        updated_dev = PhysicalDevice.parse_obj(r.json())
        self.assertEqual(updated_dev, new_dev)

        # Confirm a DAOException is raised if an invalid uid is given to update.
        new_dev.uid = -1
        payload = dev.json()
        r = requests.patch(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 404)

    def test_delete_physical_device(self):
        # Create test device, no need to check authorization as we're just testing deletion.
        dev, new_dev = self._create_physical_device(expected_code=201, req_header=self._ADMIN_HEADERS)

        url = f'{_BASE}/physical/devices/{new_dev.uid}'
        # Delete using admin headers, should return 204 no content.
        r = requests.delete(url, headers=self._ADMIN_HEADERS)
        self.assertEqual(r.status_code, 204)

        # Confirm the device was deleted.
        r = requests.get(url, headers=self._HEADERS)
        self.assertEqual(r.status_code, 404)

        # Confirm delete does not throw an exception when the device does not exist.
        r = requests.delete(url, headers=self._ADMIN_HEADERS)
        self.assertEqual(r.status_code, 404)

    def test_create_device_note(self):
        # Create test device using admin headers, no need to check auth in dev note test.
        dev, new_dev = self._create_physical_device(req_header=self._ADMIN_HEADERS)

        note1 = DeviceNote(note="Note1")
        url = f'{_BASE}/physical/devices/notes/{new_dev.uid}'
        # Test non admin user note post. Expect forbidden 403.
        r = requests.post(url, headers=self._HEADERS, data=note1.json())
        self.assertEqual(r.status_code, 403)

        # Test admin user note post. Expect 201 Created.
        r = requests.post(url, headers=self._ADMIN_HEADERS, data=note1.json())
        self.assertEqual(r.status_code, 201)

        # Test note post to non-existent device. Expect 404 Not Found.
        url = f'{_BASE}/physical/devices/notes/{-1}'
        r = requests.post(url, headers=self._ADMIN_HEADERS, data=note1.json())
        self.assertEqual(r.status_code, 404)

    def test_get_device_notes(self):
        # Create test physical device, no need to test auth.
        dev, new_dev = self._create_physical_device(req_header=self._ADMIN_HEADERS)

        note1 = DeviceNote(note="Note1")
        note2 = DeviceNote(note="Note2")
        note3 = DeviceNote(note="Note3")

        url = f'{_BASE}/physical/devices/notes/{new_dev.uid}'

        # Test non-admin user post fails
        r = requests.post(url, headers=self._HEADERS, data=note1.json())
        self.assertEqual(r.status_code, 403)

        # Test multi note post using admin authentication.
        r = requests.post(url, headers=self._ADMIN_HEADERS, data=note1.json())
        self.assertEqual(r.status_code, 201)

        time.sleep(0.01)
        r = requests.post(url, headers=self._ADMIN_HEADERS, data=note2.json())
        self.assertEqual(r.status_code, 201)

        time.sleep(0.01)
        r = requests.post(url, headers=self._ADMIN_HEADERS, data=note3.json())
        self.assertEqual(r.status_code, 201)

        # Confirm multiple notes are returned in ascending timestamp order. Using read-only token.
        r = requests.get(url, headers=self._HEADERS)
        self.assertEqual(r.status_code, 200)
        notes = [DeviceNote.parse_obj(n) for n in r.json()]
        self.assertIsNotNone(notes)
        self.assertEqual(len(notes), 3)
        self.assertLess(notes[0].ts, notes[1].ts)
        self.assertLess(notes[1].ts, notes[2].ts)

        # Confirm an empty array is returned for an invalid device id.
        url = f'{_BASE}/physical/devices/notes/{-1}'
        r = requests.get(url, headers=self._HEADERS)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 0)

    """--------------------------------------------------------------------------
    LOGICAL DEVICES
    --------------------------------------------------------------------------"""

    def _create_default_logical_device(self, expected_code=201, req_header=_HEADERS, dev=None) -> Tuple[
        LogicalDevice, LogicalDevice]:
        if dev is None:
            last_seen = self.now()
            dev = LogicalDevice(name='Test Device', location=Location(lat=3, long=-31), last_seen=last_seen,
                                properties={'appId': 'x', 'devId': 'y', 'other': 'z'})

        url = f'{_BASE}/logical/devices/'
        payload = dev.json()
        r = requests.post(url, headers=req_header, data=payload)
        self.assertEqual(r.status_code, expected_code)
        new_dev = None
        if expected_code == 201:
            new_dev = LogicalDevice.parse_obj(r.json())
            self.assertEqual(r.headers['Location'], f'{url}{new_dev.uid}')
        return (dev, new_dev)

    def test_create_logical_device(self):
        dev, new_dev = self._create_default_logical_device(expected_code=403, req_header=self._HEADERS)

        dev, new_dev = self._create_default_logical_device(expected_code=201, req_header=self._ADMIN_HEADERS)

        # Don't fail the equality assertion due to the uid being None in dev.
        dev.uid = new_dev.uid
        self.assertEqual(dev, new_dev)

    def test_get_logical_device(self):
        url = f'{_BASE}/logical/devices/1'
        # Get logical device that doesn't exist. Expect 404 Not Found.
        r = requests.get(url, headers=self._HEADERS)
        self.assertEqual(r.status_code, 404)

        # Create test device.
        dev, new_dev = self._create_default_logical_device(expected_code=201, req_header=self._ADMIN_HEADERS)

        url = f'{_BASE}/logical/devices/{new_dev.uid}'
        r = requests.get(url, headers=self._HEADERS)
        self.assertEqual(r.status_code, 200)
        got_dev = LogicalDevice.parse_obj(r.json())
        self.assertEqual(new_dev, got_dev)

    def test_update_logical_device(self):
        dev, new_dev = self._create_default_logical_device(req_header=self._ADMIN_HEADERS)

        # Confirm no update works.
        url = f"{_BASE}/logical/devices/"
        payload = new_dev.json()
        r = requests.patch(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 200)
        updated_dev = LogicalDevice.parse_obj(r.json())
        self.assertEqual(updated_dev, new_dev)

        new_dev.name = 'X'
        payload = new_dev.json()
        r = requests.patch(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 200)
        updated_dev = LogicalDevice.parse_obj(r.json())
        self.assertEqual(updated_dev, new_dev)

        new_dev.properties['q1'] = {'q2': 22}
        payload = new_dev.json()
        r = requests.patch(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 200)
        updated_dev = LogicalDevice.parse_obj(r.json())
        self.assertEqual(updated_dev, new_dev)

        # Confirm a DAOException is raised if an invalid uid is given to update.
        new_dev.uid = -1
        payload = dev.json()
        r = requests.patch(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 404)

    def test_delete_logical_device(self):
        # Create default logical device for testing logical device deletion.
        dev, new_dev = self._create_default_logical_device(expected_code=201, req_header=self._ADMIN_HEADERS)

        url = f'{_BASE}/logical/devices/{new_dev.uid}'

        # Test deletion with non-admin user.
        r = requests.delete(url, headers=self._HEADERS)
        self.assertEqual(r.status_code, 403)

        r = requests.delete(url, headers=self._ADMIN_HEADERS)
        self.assertEqual(r.status_code, 204)

        # Confirm the device was deleted.
        r = requests.get(url, headers=self._HEADERS)
        self.assertEqual(r.status_code, 404)

        # Confirm delete does not throw an exception when the device does not exist.
        r = requests.delete(url, headers=self._ADMIN_HEADERS)
        self.assertEqual(r.status_code, 404)

    def test_insert_mapping(self):
        pdev, new_pdev = self._create_physical_device(req_header=self._ADMIN_HEADERS)
        ldev, new_ldev = self._create_default_logical_device(req_header=self._ADMIN_HEADERS)
        mapping = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=self.now())

        # This should work.
        url = f'{_BASE}/mappings/'
        payload = mapping.json()
        r = requests.post(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 201)

        # This should fail due to duplicate start time.
        r = requests.post(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 400)

        # This should fail because the physical device has a current mapping.
        time.sleep(0.001)
        mapping.start_time = self.now()
        payload = mapping.json()
        r = requests.post(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 400)

        # End the current mapping and create a new one. This should work and
        # simulates 'pausing' a physical device while working on it.
        requests.patch(f'{url}physical/end/{mapping.pd.uid}', headers=self._ADMIN_HEADERS)
        mapping.start_time = self.now()
        payload = mapping.json()
        r = requests.post(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 201)

        pdx = copy.deepcopy(new_pdev)
        pdx.uid = -1
        mapping = PhysicalToLogicalMapping(pd=pdx, ld=new_ldev, start_time=self.now())
        # This should fail due to invalid physical uid.
        payload = mapping.json()
        r = requests.post(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 404)

        ldx = copy.deepcopy(new_ldev)
        ldx.uid = -1
        mapping = PhysicalToLogicalMapping(pd=new_pdev, ld=ldx, start_time=self.now())

        # End the current mapping for the phyiscal device so the RESTAPI doesn't
        # return status 400.
        requests.patch(f'{url}physical/end/{mapping.pd.uid}', headers=self._ADMIN_HEADERS)

        # This should fail due to invalid logical uid.
        payload = mapping.json()
        r = requests.post(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 404)

    def test_get_mapping_from_physical(self):
        pdev, new_pdev = self._create_physical_device(req_header=self._ADMIN_HEADERS)
        ldev, new_ldev = self._create_default_logical_device(req_header=self._ADMIN_HEADERS)
        mapping = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=self.now())

        url = f'{_BASE}/mappings/'
        payload = mapping.json()
        r = requests.post(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 201)

        # Confirm getting the mapping works.
        r = requests.get(f'{url}physical/current/{new_pdev.uid}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 200)
        m = PhysicalToLogicalMapping.parse_obj(r.json())
        self.assertEqual(mapping, m)

        # Confirm getting an invalid map returns 404
        r = requests.get(f'{url}physical/current/{-1}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 404)

        # End the current mapping for the phyiscal device so the RESTAPI doesn't
        # return status 400.
        requests.patch(f'{url}physical/end/{mapping.pd.uid}', headers=self._ADMIN_HEADERS)

        # Confirm the latest mapping is returned.
        time.sleep(0.001)
        mapping2 = copy.deepcopy(mapping)
        mapping2.start_time = self.now()
        self.assertNotEqual(mapping, mapping2)
        payload = mapping2.json()
        r = requests.post(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 201)

        r = requests.get(f'{url}physical/current/{new_pdev.uid}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 200)
        m = PhysicalToLogicalMapping.parse_obj(r.json())
        self.assertEqual(mapping2, m)

    def test_get_mapping_from_logical(self):
        pdev, new_pdev = self._create_physical_device(req_header=self._ADMIN_HEADERS)
        ldev, new_ldev = self._create_default_logical_device(req_header=self._ADMIN_HEADERS)
        mapping = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=self.now())

        url = f'{_BASE}/mappings/'
        payload = mapping.json()
        r = requests.post(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 201)

        # Confirm getting the mapping works.
        r = requests.get(f'{url}logical/current/{new_ldev.uid}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 200)
        m = PhysicalToLogicalMapping.parse_obj(r.json())
        self.assertEqual(mapping, m)

        # Confirm getting an invalid map returns 404
        r = requests.get(f'{url}logical/current/{-1}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 404)

        # End the current mapping for the phyiscal device so the RESTAPI doesn't
        # return status 400.
        requests.patch(f'{url}logical/end/{mapping.ld.uid}', headers=self._ADMIN_HEADERS)

        # Confirm the latest mapping is returned.
        time.sleep(0.001)
        mapping2 = copy.deepcopy(mapping)
        mapping2.start_time = self.now()
        self.assertNotEqual(mapping, mapping2)
        payload = mapping2.json()
        r = requests.post(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 201)

        r = requests.get(f'{url}logical/current/{new_ldev.uid}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 200)
        m = PhysicalToLogicalMapping.parse_obj(r.json())
        self.assertEqual(mapping2, m)

    def compare_mappings_ignore_end_time(self, m1: PhysicalToLogicalMapping, m2: PhysicalToLogicalMapping) -> bool:
        return m1.pd == m2.pd and m1.ld == m2.ld and m1.start_time == m2.start_time

    def test_get_latest_mapping_from_physical(self):
        pdev, new_pdev = self._create_physical_device(req_header=self._ADMIN_HEADERS)
        ldev, new_ldev = self._create_default_logical_device(req_header=self._ADMIN_HEADERS)
        mapping = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=self.now())

        url = f'{_BASE}/mappings/'

        # No mappings yet, these should both 404.
        r = requests.get(f'{url}physical/current/{new_pdev.uid}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 404)

        r = requests.get(f'{url}physical/latest/{new_pdev.uid}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 404)

        payload = mapping.json()
        r = requests.post(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 201)

        # Confirm getting the mapping works via current.
        r = requests.get(f'{url}physical/current/{new_pdev.uid}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 200)
        m = PhysicalToLogicalMapping.parse_obj(r.json())
        self.assertEqual(mapping, m)

        # Confirm getting the mapping works via latest.
        r = requests.get(f'{url}physical/latest/{new_pdev.uid}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 200)
        m = PhysicalToLogicalMapping.parse_obj(r.json())
        self.assertEqual(mapping, m)

        # End the mapping to test that current returns None but latest returns the finished mapping.
        requests.patch(f'{url}physical/end/{mapping.pd.uid}', headers=self._ADMIN_HEADERS)

        # Confirm getting the current mapping ignores the finished map row.
        r = requests.get(f'{url}physical/current/{new_pdev.uid}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 404)

        # Confirm getting the mapping works via latest.
        r = requests.get(f'{url}physical/latest/{new_pdev.uid}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 200)
        m = PhysicalToLogicalMapping.parse_obj(r.json())
        self.assertIsNotNone(m.end_time)
        self.assertTrue(self.compare_mappings_ignore_end_time(mapping, m))

    def test_get_latest_mapping_from_logical(self):
        pdev, new_pdev = self._create_physical_device(req_header=self._ADMIN_HEADERS)
        ldev, new_ldev = self._create_default_logical_device(req_header=self._ADMIN_HEADERS)
        mapping = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=self.now())

        url = f'{_BASE}/mappings/'

        # No mappings yet, these should both 404.
        r = requests.get(f'{url}logical/current/{new_ldev.uid}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 404)

        r = requests.get(f'{url}logical/latest/{new_ldev.uid}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 404)

        payload = mapping.json()
        r = requests.post(url, headers=self._ADMIN_HEADERS, data=payload)
        self.assertEqual(r.status_code, 201)

        # Confirm getting the mapping works via current.
        r = requests.get(f'{url}logical/current/{new_ldev.uid}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 200)
        m = PhysicalToLogicalMapping.parse_obj(r.json())
        self.assertEqual(mapping, m)

        # Confirm getting the mapping works via latest.
        r = requests.get(f'{url}logical/latest/{new_ldev.uid}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 200)
        m = PhysicalToLogicalMapping.parse_obj(r.json())
        self.assertEqual(mapping, m)

        # End the mapping to test that current returns None but latest returns the finished mapping.
        requests.patch(f'{url}logical/end/{new_ldev.uid}', headers=self._ADMIN_HEADERS)

        # Confirm getting the current mapping ignores the finished map row.
        r = requests.get(f'{url}logical/current/{new_ldev.uid}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 404)

        # Confirm getting the mapping works via latest.
        r = requests.get(f'{url}logical/latest/{new_ldev.uid}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 200)
        m = PhysicalToLogicalMapping.parse_obj(r.json())
        self.assertIsNotNone(m.end_time)
        self.assertTrue(self.compare_mappings_ignore_end_time(mapping, m))

    def test_get_all_logical_device_mappings(self):
        # Create physical and logical devices for test.
        pdev, new_pdev = self._create_physical_device(req_header=self._ADMIN_HEADERS)
        ldev, new_ldev = self._create_default_logical_device(req_header=self._ADMIN_HEADERS)

        # Using the DAO to create the test data, the REST API methods to do this are
        # tested elsewhere.

        mapping1 = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=self.now())
        dao.insert_mapping(mapping1)
        time.sleep(0.1)
        dao.end_mapping(ld=new_ldev.uid)
        mapping1 = dao.get_current_device_mapping(ld=new_ldev.uid, only_current_mapping=False)

        pdev2 = copy.deepcopy(pdev)
        pdev2.name = 'D2'
        pdev2, new_pdev2 = self._create_physical_device(dev=pdev2, req_header=self._ADMIN_HEADERS)
        time.sleep(0.1)
        mapping2 = PhysicalToLogicalMapping(pd=new_pdev2, ld=new_ldev, start_time=self.now())
        dao.insert_mapping(mapping2)
        time.sleep(0.1)
        dao.end_mapping(ld=new_ldev.uid)
        mapping2 = dao.get_current_device_mapping(ld=new_ldev.uid, only_current_mapping=False)

        pdev3 = copy.deepcopy(pdev)
        pdev3.name = 'D3'
        pdev3, new_pdev3 = self._create_physical_device(dev=pdev3, req_header=self._ADMIN_HEADERS)
        time.sleep(0.1)
        mapping3 = PhysicalToLogicalMapping(pd=new_pdev3, ld=new_ldev, start_time=self.now())
        dao.insert_mapping(mapping3)

        url = f'{_BASE}/mappings/logical/all/{new_ldev.uid}'
        r = requests.get(f'{url}', headers=self._HEADERS)
        self.assertEqual(r.status_code, 200)

        j = r.json()
        self.assertIsNotNone(j)
        self.assertEqual(len(j), 3)

        # Note the devs must be parsed by the PhysicalDevice class to convert
        # the ISO-8601 strings into datetime objects or the comparsion will not
        # work.
        mappings = [PhysicalToLogicalMapping.parse_obj(m) for m in j]

        self.assertEqual(len(mappings), 3)
        self.assertEqual(mappings[0], mapping3)
        self.assertEqual(mappings[1], mapping2)
        self.assertEqual(mappings[2], mapping1)

    def test_get_auth_token(self):
        test_uname = os.urandom(4).hex()
        dao.user_add(uname=test_uname, passwd='password', disabled=False)

        headers = self._HEADERS
        headers['Authorization'] = f'Basic {base64.b64encode(f"{test_uname}:password".encode()).decode()}'
        url = f"{_BASE}/token"
        r = requests.get(url, headers=headers)
        self.assertEqual(r.status_code, 200)

    def test_user_login(self):
        # Create user for testing
        test_uname = os.urandom(4).hex()
        dao.user_add(uname=test_uname, passwd='password', disabled=False)

        # Get auth token
        headers = self._HEADERS
        headers['Authorization'] = f'Basic {base64.b64encode(f"{test_uname}:password".encode()).decode()}'
        url = f"{_BASE}/token"
        r = requests.get(url, headers=headers)
        token = r.text.strip('"')

        # Test token on /physical/sources
        url = f"{_BASE}/physical/sources"
        headers = self._HEADERS
        headers['Authorization'] = f'Bearer {token}'
        r = requests.get(url, headers=self._HEADERS)

        self.assertEqual(r.status_code, 200)


if __name__ == '__main__':
    unittest.main()