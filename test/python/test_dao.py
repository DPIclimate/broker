import copy, datetime, logging, time, unittest, uuid, warnings, dateutil.parser

import BrokerConstants
import api.client.DAO as dao
from pdmodels.Models import PhysicalDevice, PhysicalToLogicalMapping, Location, LogicalDevice
from typing import Tuple
import os
import pprint as pp

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
logger = logging.getLogger(__name__)
logging.captureWarnings(True)


def _create_test_user() -> str:
    test_uname=os.urandom(4).hex()
    dao.user_add(uname=test_uname, passwd='password', disabled=False)
    return test_uname


def _now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


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
                    truncate physical_timeseries cascade;
                    truncate raw_messages cascade;
                    delete from sources where source_name = 'axistech';''')
        finally:
            dao.free_conn(conn)

    def test_get_all_physical_sources(self):
        sources = dao.get_all_physical_sources()
        self.assertEqual(sources, ['greenbrain', 'ict_eagleio', 'ttn', 'wombat', 'ydoc'])

    def test_add_physical_source(self):
        sources = dao.get_all_physical_sources()
        self.assertFalse(BrokerConstants.AXISTECH in sources)
        dao.add_physical_source(BrokerConstants.AXISTECH)
        sources = dao.get_all_physical_sources()
        self.assertTrue(BrokerConstants.AXISTECH in sources)

        # Do it again to ensure it doesn't crash, and there is only one instance of the string.
        dao.add_physical_source(BrokerConstants.AXISTECH)
        sources = dao.get_all_physical_sources()
        i = 0
        for s in sources:
            if s == BrokerConstants.AXISTECH:
                i += 1

        self.assertEqual(1, i)

    def _create_physical_device(self, dev: PhysicalDevice = None) -> Tuple[PhysicalDevice, PhysicalDevice]:
        last_seen = _now()
        if dev is None:
            dev = PhysicalDevice(source_name='ttn', name='Test Device', location=Location(lat=3, long=-31), last_seen=last_seen,
                source_ids={'appId': 'x', 'devId': 'y'},
                properties={'appId': 'x', 'devId': 'y', 'other': 'z'})

        return (dev, dao.create_physical_device(dev))

    def test_create_physical_device(self):
        dev, new_dev = self._create_physical_device()

        # Don't fail the equality assertion due to the uid being None in dev.
        dev.uid = new_dev.uid
        self.assertEqual(dev, new_dev)

    def test_get_physical_device(self):
        dev, new_dev = self._create_physical_device()

        got_dev = dao.get_physical_device(new_dev.uid)
        self.assertEqual(new_dev, got_dev)

        dev = dao.get_physical_device(-1)
        self.assertIsNone(dev)

    def test_get_physical_device_using_source_ids(self):
        dev, new_dev = self._create_physical_device()

        # Create an otherwise similar device from a different source to verify
        # the source_name is taken into account by the dao method.
        dev.source_name = 'greenbrain'
        gb_dev = dao.create_physical_device(dev)

        got_devs = dao.get_pyhsical_devices_using_source_ids('ttn', {'appId': 'x'})
        self.assertEqual(len(got_devs), 1)
        self.assertEqual(new_dev, got_devs[0])

        got_devs = dao.get_pyhsical_devices_using_source_ids('ttn', {'devId': 'y'})
        self.assertEqual(len(got_devs), 1)
        self.assertEqual(new_dev, got_devs[0])

        got_devs = dao.get_pyhsical_devices_using_source_ids('ttn', {'devId': 'x'})
        self.assertEqual(len(got_devs), 0)

        # Confirm multiple devices are returned for a common source id attribute.
        dev.source_name = 'ttn'
        dev.source_ids['devId'] = 'z'
        new_dev2 = dao.create_physical_device(dev)
        got_devs = dao.get_pyhsical_devices_using_source_ids('ttn', {'appId': 'x'})
        self.assertEqual(len(got_devs), 2)
        self.assertEqual(new_dev, got_devs[0])
        self.assertEqual(new_dev2, got_devs[1])

        # Confirm a more specific set of attributes works.
        got_devs = dao.get_pyhsical_devices_using_source_ids('ttn', {'appId': 'x', 'devId': 'y'})
        self.assertEqual(len(got_devs), 1)
        self.assertEqual(new_dev, got_devs[0])

        # Confirm the source selector works - already tested above but doesn't hurt to
        # see we can get other device sources.
        got_devs = dao.get_pyhsical_devices_using_source_ids('greenbrain', {'appId': 'x'})
        self.assertEqual(len(got_devs), 1)
        self.assertEqual(gb_dev, got_devs[0])


    def test_update_physical_device(self):
        dev, new_dev = self._create_physical_device()

        # Confirm no update works.
        updated_dev = dao.update_physical_device(new_dev)
        self.assertEqual(updated_dev, new_dev)

        new_dev.name = 'X'
        updated_dev = dao.update_physical_device(new_dev)
        self.assertEqual(updated_dev, new_dev)

        new_dev.properties['q1'] = {'q2': 22}
        updated_dev = dao.update_physical_device(new_dev)
        self.assertEqual(updated_dev, new_dev)

        # Confirm a DAODeviceNotFound is raised if an invalid uid is given to update.
        new_dev.uid = -1
        self.assertRaises(dao.DAODeviceNotFound, dao.update_physical_device, new_dev)

    def test_delete_physical_device(self):
        dev, new_dev = self._create_physical_device()
        self.assertEqual(dao.delete_physical_device(new_dev.uid), new_dev)

        # Confirm the device was deleted.
        self.assertIsNone(dao.get_physical_device(new_dev.uid))

        # Confirm delete does not throw an exception when the device does not exist.
        self.assertIsNone(dao.delete_physical_device(new_dev.uid))

    def test_create_physical_device_note(self):
        dev, new_dev = self._create_physical_device()
        dao.create_physical_device_note(new_dev.uid, 'Note 1')
        dao.create_physical_device_note(new_dev.uid, 'Note 2')

        self.assertRaises(dao.DAODeviceNotFound, dao.create_physical_device_note, -1, 'Note 1')

    def test_get_physical_device_notes(self):
        dev, new_dev = self._create_physical_device()
        dao.create_physical_device_note(new_dev.uid, 'Note 1')
        time.sleep(0.001)
        dao.create_physical_device_note(new_dev.uid, 'Note 2')

        # Creates a new physical device row with a new uid, does not matter
        # the other fields are the same.
        new_dev2 = dao.create_physical_device(dev)
        dao.create_physical_device_note(new_dev2.uid, 'Note 3')

        notes = dao.get_physical_device_notes(new_dev.uid)
        self.assertEqual(len(notes), 2)
        self.assertGreater(notes[1].ts, notes[0].ts)
        self.assertEqual(notes[0].note, 'Note 1')
        self.assertEqual(notes[1].note, 'Note 2')

        notes = dao.get_physical_device_notes(new_dev2.uid)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].note, 'Note 3')

        notes = dao.get_physical_device_notes(-1)
        self.assertEqual(len(notes), 0)

    def test_update_physical_device_note(self):
        dev, new_dev = self._create_physical_device()
        dao.create_physical_device_note(new_dev.uid, 'Note 1')
        time.sleep(0.001)
        dao.create_physical_device_note(new_dev.uid, 'Note 2')

        notes = dao.get_physical_device_notes(new_dev.uid)
        self.assertEqual(len(notes), 2)
        self.assertGreater(notes[1].ts, notes[0].ts)
        self.assertEqual(notes[0].note, 'Note 1')
        self.assertEqual(notes[1].note, 'Note 2')

        notes[0].note = 'XYZ'
        dao.update_physical_device_note(notes[0])
        notes = dao.get_physical_device_notes(new_dev.uid)
        self.assertEqual(len(notes), 2)
        self.assertGreater(notes[1].ts, notes[0].ts)
        self.assertEqual(notes[0].note, 'XYZ')
        self.assertEqual(notes[1].note, 'Note 2')

    def test_delete_physical_device_note(self):
        dev, new_dev = self._create_physical_device()
        dao.create_physical_device_note(new_dev.uid, 'Note 1')
        time.sleep(0.001)
        dao.create_physical_device_note(new_dev.uid, 'Note 2')

        notes = dao.get_physical_device_notes(new_dev.uid)
        self.assertEqual(len(notes), 2)
        self.assertGreater(notes[1].ts, notes[0].ts)
        self.assertEqual(notes[0].note, 'Note 1')
        self.assertEqual(notes[1].note, 'Note 2')

        dao.delete_physical_device_note(notes[0].uid)

        notes = dao.get_physical_device_notes(new_dev.uid)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].note, 'Note 2')

    def _create_default_logical_device(self, dev=None) -> Tuple[LogicalDevice, LogicalDevice]:
        if dev is None:
            last_seen = _now()
            dev = LogicalDevice(name='Test Device', location=Location(lat=3, long=-31), last_seen=last_seen,
                properties={'appId': 'x', 'devId': 'y', 'other': 'z'})

        return (dev, dao.create_logical_device(dev))

    def test_create_logical_device(self):
        dev, new_dev = self._create_default_logical_device()

        # Don't fail the equality assertion due to the uid being None in dev.
        dev.uid = new_dev.uid
        self.assertEqual(dev, new_dev)

    def test_get_logical_device(self):
        dev, new_dev = self._create_default_logical_device()

        got_dev = dao.get_logical_device(new_dev.uid)
        self.assertEqual(new_dev, got_dev)

        dev = dao.get_logical_device(-1)
        self.assertIsNone(dev)

    def test_update_logical_device(self):
        dev, new_dev = self._create_default_logical_device()

        # Confirm no update because device has not changed works.
        updated_dev = dao.update_logical_device(new_dev)
        self.assertEqual(updated_dev, new_dev)

        new_dev.name = 'X'
        updated_dev = dao.update_logical_device(new_dev)
        self.assertEqual(updated_dev, new_dev)

        new_dev.properties['q1'] = {'q2': 22}
        updated_dev = dao.update_logical_device(new_dev)
        self.assertEqual(updated_dev, new_dev)

        # Confirm a DAODeviceNotFound is raised if an invalid uid is given to update.
        new_dev.uid = -1
        self.assertRaises(dao.DAODeviceNotFound, dao.update_logical_device, new_dev)

    def test_delete_logical_device(self):
        dev, new_dev = self._create_default_logical_device()
        self.assertEqual(dao.delete_logical_device(new_dev.uid), new_dev)

        # Confirm the device was deleted.
        self.assertIsNone(dao.get_logical_device(new_dev.uid))

        # Confirm delete does not throw an exception when the device does not exist.
        self.assertIsNone(dao.delete_logical_device(new_dev.uid))

    def test_insert_mapping(self):
        pdev, new_pdev = self._create_physical_device()
        ldev, new_ldev = self._create_default_logical_device()
        mapping = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=_now())

        # This should work.
        dao.insert_mapping(mapping)

        # This should fail due to duplicate start time.
        self.assertRaises(ValueError, dao.insert_mapping, mapping)

        # This should fail due to the physical device is still mapped to something.
        time.sleep(0.001)
        mapping.start_time= _now()
        self.assertRaises(ValueError, dao.insert_mapping, mapping)

        # Unmap the physical device so the next test doesn't fail due to the device being mapped.
        dao.end_mapping(pd=new_pdev)
        # The insert_mapping operation should succeed because the timestamp is different from above.
        mapping.start_time= _now()
        dao.insert_mapping(mapping)

        pdx = copy.deepcopy(new_pdev)
        pdx.uid = -1
        mapping = PhysicalToLogicalMapping(pd=pdx, ld=new_ldev, start_time=_now())
        # This should fail due to invalid physical uid.
        self.assertRaises(dao.DAODeviceNotFound, dao.insert_mapping, mapping)

        # Unmap the physical device so the next test doesn't fail due to the device being mapped.
        dao.end_mapping(pd=new_pdev)
        ldx = copy.deepcopy(new_ldev)
        ldx.uid = -1
        mapping = PhysicalToLogicalMapping(pd=new_pdev, ld=ldx, start_time=_now())
        # This should fail due to invalid logical uid.
        self.assertRaises(dao.DAODeviceNotFound, dao.insert_mapping, mapping)

    def test_get_current_device_mapping(self):
        pdev, new_pdev = self._create_physical_device()
        ldev, new_ldev = self._create_default_logical_device()

        # No mapping yet, confirm all forms of call return None.
        self.assertIsNone(dao.get_current_device_mapping(pd=-1))
        self.assertIsNone(dao.get_current_device_mapping(pd=new_pdev))

        self.assertIsNone(dao.get_current_device_mapping(ld=-1))
        self.assertIsNone(dao.get_current_device_mapping(ld=new_ldev))

        # Confirm pd or ld must be given.
        self.assertRaises(ValueError, dao.get_current_device_mapping)

        # Confirm only pd or ld can be given.
        self.assertRaises(ValueError, dao.get_current_device_mapping, -1, -1)
        self.assertRaises(ValueError, dao.get_current_device_mapping, new_pdev, new_ldev)

        # confirm a physical device can be mapped to a logical device.
        mapping1 = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=_now())
        dao.insert_mapping(mapping1)

        self.assertEqual(mapping1, dao.get_current_device_mapping(pd=new_pdev.uid))
        self.assertEqual(mapping1, dao.get_current_device_mapping(pd=new_pdev))
        self.assertEqual(mapping1, dao.get_current_device_mapping(ld=new_ldev.uid))
        self.assertEqual(mapping1, dao.get_current_device_mapping(ld=new_ldev))

        # Confirm mapping a new physical device to the same logical device overrides the
        # original mapping.
        time.sleep(0.001)
        pdev2, new_pdev2 = self._create_physical_device()

        mapping2 = PhysicalToLogicalMapping(pd=new_pdev2, ld=new_ldev, start_time=_now())
        dao.insert_mapping(mapping2)

        # This test must fail if multiple mappings are found, because there should not be
        # multiple mappings. In practice the system will return the latest mapping but failing
        # here shows the mapping end_date is not being updated.
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('error')

            self.assertEqual(mapping2, dao.get_current_device_mapping(pd=new_pdev2.uid))
            self.assertEqual(mapping2, dao.get_current_device_mapping(pd=new_pdev2))
            self.assertEqual(mapping2, dao.get_current_device_mapping(ld=new_ldev.uid))
            self.assertEqual(mapping2, dao.get_current_device_mapping(ld=new_ldev))

    def test_get_latest_device_mapping(self):
        pdev, new_pdev = self._create_physical_device()
        ldev, new_ldev = self._create_default_logical_device()

        # confirm getting the latest mapping returns a current mapping
        mapping1 = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=_now())
        dao.insert_mapping(mapping1)

        self.assertEqual(mapping1, dao.get_current_device_mapping(pd=new_pdev.uid, only_current_mapping=True))
        self.assertEqual(mapping1, dao.get_current_device_mapping(pd=new_pdev, only_current_mapping=True))
        self.assertEqual(mapping1, dao.get_current_device_mapping(ld=new_ldev.uid, only_current_mapping=True))
        self.assertEqual(mapping1, dao.get_current_device_mapping(ld=new_ldev, only_current_mapping=True))

        self.assertEqual(mapping1, dao.get_current_device_mapping(pd=new_pdev.uid, only_current_mapping=False))
        self.assertEqual(mapping1, dao.get_current_device_mapping(pd=new_pdev, only_current_mapping=False))
        self.assertEqual(mapping1, dao.get_current_device_mapping(ld=new_ldev.uid, only_current_mapping=False))
        self.assertEqual(mapping1, dao.get_current_device_mapping(ld=new_ldev, only_current_mapping=False))

        dao.end_mapping(mapping1.pd.uid)

        # the default call will return None because the mapping has ended
        mapping2 = dao.get_current_device_mapping(pd=mapping1.pd.uid)
        self.assertIsNone(mapping2)

        # asking for the most recent mapping, even if it has ended, should return mapping1 but
        # with an end time.
        mapping2 = dao.get_current_device_mapping(pd=mapping1.pd.uid, only_current_mapping=False)
        self.assertIsNotNone(mapping2.end_time)
        self.assertTrue(self.compare_mappings_ignore_end_time(mapping1, mapping2))

        time.sleep(0.1)
        mapping1.start_time = _now()
        dao.insert_mapping(mapping1)

        # with a new mapping with no end time, both calls should again return the same thing.
        mapping3 = dao.get_current_device_mapping(pd=mapping1.pd.uid)
        self.assertEqual(mapping1, mapping3)

        mapping3 = dao.get_current_device_mapping(pd=mapping1.pd.uid, only_current_mapping=False)
        self.assertEqual(mapping1, mapping3)

    def test_end_mapping(self):
        pdev, new_pdev = self._create_physical_device()
        ldev, new_ldev = self._create_default_logical_device()

        # Confirm pd or ld must be given.
        self.assertRaises(ValueError, dao.end_mapping)

        # Confirm only pd or ld can be given.
        self.assertRaises(ValueError, dao.end_mapping, -1, -1)
        self.assertRaises(ValueError, dao.end_mapping, new_pdev, new_ldev)

        mapping1 = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=_now())
        dao.insert_mapping(mapping1)

        mappings = dao.get_unmapped_physical_devices()
        self.assertEqual(len(mappings), 0)

        dao.end_mapping(pd=new_pdev.uid)
        mappings = dao.get_unmapped_physical_devices()
        self.assertEqual(len(mappings), 1)

        pdev2 = copy.deepcopy(pdev)
        pdev2.name = 'D2'
        pdev2, new_pdev2 = self._create_physical_device(dev=pdev2)
        mapping2 = PhysicalToLogicalMapping(pd=new_pdev2, ld=new_ldev, start_time=_now())

        dao.insert_mapping(mapping2)
        mappings = dao.get_unmapped_physical_devices()
        self.assertEqual(len(mappings), 1)

        dao.end_mapping(ld=new_ldev.uid)
        mappings = dao.get_unmapped_physical_devices()
        self.assertEqual(len(mappings), 2)

        # Avoid a unique key constraint due to identical timestamps.
        time.sleep(0.001)
        mapping1.start_time = _now()
        dao.insert_mapping(mapping1)
        dao.end_mapping(pd=new_pdev)
        mappings = dao.get_unmapped_physical_devices()
        self.assertEqual(len(mappings), 2)

        mapping2.start_time = _now()
        dao.insert_mapping(mapping2)
        mappings = dao.get_unmapped_physical_devices()
        self.assertEqual(len(mappings), 1)

        dao.end_mapping(ld=new_ldev)
        mappings = dao.get_unmapped_physical_devices()
        self.assertEqual(len(mappings), 2)

    def compare_mappings_ignore_end_time(self, m1: PhysicalToLogicalMapping, m2: PhysicalToLogicalMapping) -> bool:
        return m1.pd == m2.pd and m1.ld == m2.ld and m1.start_time == m2.start_time

    def test_get_mappings(self):
        pdev, new_pdev = self._create_physical_device()
        ldev, new_ldev = self._create_default_logical_device()
        mapping1 = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=_now())
        dao.insert_mapping(mapping1)

        pdev2 = copy.deepcopy(pdev)
        pdev2.name = 'D2'
        pdev2, new_pdev2 = self._create_physical_device(dev=pdev2)
        time.sleep(0.1)
        mapping2 = PhysicalToLogicalMapping(pd=new_pdev2, ld=new_ldev, start_time=_now())
        dao.insert_mapping(mapping2)

        # Avoid a unique key constraint due to identical timestamps.
        time.sleep(0.1)
        mapping3 = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=_now())
        dao.insert_mapping(mapping3)

        mappings = dao.get_logical_device_mappings(new_ldev)
        self.assertEqual(len(mappings), 3)

        self.assertTrue(self.compare_mappings_ignore_end_time(mappings[0], mapping3))
        self.assertTrue(self.compare_mappings_ignore_end_time(mappings[1], mapping2))
        self.assertTrue(self.compare_mappings_ignore_end_time(mappings[2], mapping1))

    def test_get_all_logical_device_mappings(self):
        pdev, new_pdev = self._create_physical_device()
        ldev, new_ldev = self._create_default_logical_device()

        mapping1 = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=_now())
        dao.insert_mapping(mapping1)
        time.sleep(0.1)
        dao.end_mapping(ld=new_ldev.uid)
        mapping1 = dao.get_current_device_mapping(ld=new_ldev.uid, only_current_mapping=False)

        pdev2 = copy.deepcopy(pdev)
        pdev2.name = 'D2'
        pdev2, new_pdev2 = self._create_physical_device(dev=pdev2)
        time.sleep(0.1)
        mapping2 = PhysicalToLogicalMapping(pd=new_pdev2, ld=new_ldev, start_time=_now())
        dao.insert_mapping(mapping2)
        time.sleep(0.1)
        dao.end_mapping(ld=new_ldev.uid)
        mapping2 = dao.get_current_device_mapping(ld=new_ldev.uid, only_current_mapping=False)

        pdev3 = copy.deepcopy(pdev)
        pdev3.name = 'D3'
        pdev3, new_pdev3 = self._create_physical_device(dev=pdev3)
        time.sleep(0.1)
        mapping3 = PhysicalToLogicalMapping(pd=new_pdev3, ld=new_ldev, start_time=_now())
        dao.insert_mapping(mapping3)

        mappings = dao.get_logical_device_mappings(ld=new_ldev.uid)
        self.assertEqual(len(mappings), 3)
        self.assertEqual(mappings[0], mapping3)
        self.assertEqual(mappings[1], mapping2)
        self.assertEqual(mappings[2], mapping1)

    def test_get_unmapped_devices(self):
        pdev, new_pdev = self._create_physical_device()
        ldev, new_ldev = self._create_default_logical_device()

        # confirm a physical device can be mapped to a logical device.
        mapping1 = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=_now())
        dao.insert_mapping(mapping1)

        pdev2 = copy.deepcopy(pdev)
        pdev2.name = 'D2'
        pdev2, new_pdev2 = self._create_physical_device(dev=pdev2)

        pdev3 = copy.deepcopy(pdev)
        pdev3.source_name = 'greenbrain'
        pdev3.name = 'D3'
        pdev3, new_pdev3 = self._create_physical_device(dev=pdev3)

        pdev4 = copy.deepcopy(pdev)
        pdev4.source_name = 'ydoc'
        pdev4.name = 'D4'
        pdev4, new_pdev4 = self._create_physical_device(dev=pdev4)

        unmapped_devs = dao.get_unmapped_physical_devices()
        self.assertEqual(len(unmapped_devs), 3)
        self.assertTrue(new_pdev2 in unmapped_devs)
        self.assertTrue(new_pdev3 in unmapped_devs)
        self.assertTrue(new_pdev4 in unmapped_devs)

        mapping2 = PhysicalToLogicalMapping(pd=new_pdev2, ld=new_ldev, start_time=_now())
        dao.insert_mapping(mapping2)

        ldev2 = copy.deepcopy(ldev)
        ldev2.name = 'L2'
        ldev2.last_seen = _now()
        ldev2, new_ldev2 = self._create_default_logical_device(dev=ldev2)

        mapping3 = PhysicalToLogicalMapping(pd=new_pdev4, ld=new_ldev2, start_time=_now())
        dao.insert_mapping(mapping3)
        unmapped_devs = dao.get_unmapped_physical_devices()
        self.assertEqual(len(unmapped_devs), 2)
        self.assertTrue(new_pdev in unmapped_devs)
        self.assertTrue(new_pdev3 in unmapped_devs)

        ldev3 = copy.deepcopy(ldev)
        ldev3.name = 'L3'
        ldev3.last_seen = _now()
        ldev3, new_ldev3 = self._create_default_logical_device(dev=ldev3)

        mapping4 = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev3, start_time=_now())
        dao.insert_mapping(mapping4)
        unmapped_devs = dao.get_unmapped_physical_devices()
        self.assertEqual(len(unmapped_devs), 1)
        self.assertTrue(new_pdev3 in unmapped_devs)


    def test_add_raw_json_message(self):
        uuid1 = uuid.uuid4()
        obj1 = {'a': 1, 'b': '2', 'c': True, 'd': False}
        dao.add_raw_json_message('ttn', _now(), uuid1, obj1)

        uuid2 = uuid.uuid4()
        obj2 = {'a': 1, 'b': '2', 'c': False, 'd': True}
        dao.add_raw_json_message('ttn', _now(), uuid2, obj2, 1)

        with dao._get_connection() as conn, conn.cursor() as cursor:
            cursor.execute('select physical_uid, correlation_id, json_msg from raw_messages order by uid asc')
            self.assertEqual(2, cursor.rowcount)

            p_uid, c_id, msg = cursor.fetchone()
            self.assertIsNone(p_uid)
            self.assertEqual(c_id, uuid1)
            self.assertEqual(msg, obj1)

            p_uid, c_id, msg = cursor.fetchone()
            self.assertEqual(p_uid, 1)
            self.assertEqual(c_id, uuid2)
            self.assertEqual(msg, obj2)

        # Confirm the DAO raises a warning when trying to add a message with a
        # duplicate UUID, but doesn't throw an exception.
        with self.assertWarns(UserWarning):
            dao.add_raw_json_message('ttn', _now(), uuid1, obj1)


    def test_insert_physical_timeseries_message(self):
        dev, new_dev = self._create_physical_device()

        msg = {
            "p_uid": new_dev.uid,
            "timestamp": "2023-02-20T07:57:52Z",
            "timeseries": [
                {
                    "name": "x",
                    "value": 35.1
                }
            ],
            "broker_correlation_id": "3d7762f6-bcc6-44d4-82ba-49b07e61e601"
        }

        msg_ts = dateutil.parser.isoparse(msg[BrokerConstants.TIMESTAMP_KEY])
        dao.insert_physical_timeseries_message(msg)

        with dao._get_connection() as conn, conn.cursor() as cursor:
            cursor.execute('select physical_uid, ts, json_msg from physical_timeseries')
            phys_uid, ts, retrieved_msg = cursor.fetchone()
            self.assertEqual(phys_uid, msg[BrokerConstants.PHYSICAL_DEVICE_UID_KEY])
            self.assertEqual(ts, msg_ts)
            self.assertEqual(msg, retrieved_msg)

    def test_get_physical_timeseries_messages(self):
        _, new_pdev = self._create_physical_device()

        # Basic smoke test - no messages, no results.
        msgs = dao.get_physical_timeseries_message(None, None, 1, only_timestamp=True, p_uid=new_pdev.uid)
        self.assertSequenceEqual(msgs, [])

        msgs = dao.get_physical_timeseries_message(None, None, 1, only_timestamp=True, l_uid=20)
        self.assertSequenceEqual(msgs, [])

        msg_list = [
            {BrokerConstants.PHYSICAL_DEVICE_UID_KEY: new_pdev.uid, BrokerConstants.TIMESTAMP_KEY: "2023-02-20T01:00+11:00"},
            {BrokerConstants.PHYSICAL_DEVICE_UID_KEY: new_pdev.uid, BrokerConstants.TIMESTAMP_KEY: "2023-02-20T00:30+11:00"},
            {BrokerConstants.PHYSICAL_DEVICE_UID_KEY: new_pdev.uid, BrokerConstants.TIMESTAMP_KEY: "2023-02-20T00:00+11:00"},
            {BrokerConstants.PHYSICAL_DEVICE_UID_KEY: new_pdev.uid, BrokerConstants.TIMESTAMP_KEY: "2023-02-19T23:30+11:00"},
            {BrokerConstants.PHYSICAL_DEVICE_UID_KEY: new_pdev.uid, BrokerConstants.TIMESTAMP_KEY: "2023-02-19T23:00+11:00"},
            {BrokerConstants.PHYSICAL_DEVICE_UID_KEY: new_pdev.uid, BrokerConstants.TIMESTAMP_KEY: "2023-02-19T22:30+11:00"}
        ]

        msg_ts = []
        for msg in msg_list:
            dao.insert_physical_timeseries_message(msg)
            msg_ts.append(dateutil.parser.isoparse(msg[BrokerConstants.TIMESTAMP_KEY]))

        msgs = dao.get_physical_timeseries_message(None, None, 1, only_timestamp=True, p_uid=new_pdev.uid)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0], msg_ts[0])

        msgs = dao.get_physical_timeseries_message(None, None, None, only_timestamp=True, p_uid=new_pdev.uid)

        self.assertEqual(len(msgs), len(msg_list))
        for i, ts in enumerate(msgs):
            self.assertEqual(ts, msg_ts[i])

        _, new_ldev = self._create_default_logical_device()
        mapping = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=_now())
        dao.insert_mapping(mapping)

        # Ensure 1 message will be returned from the DAO when no start or end is given.
        now = _now() - datetime.timedelta(minutes=1)
        td_30_mins = datetime.timedelta(minutes=30)

        for i, msg in enumerate(msg_list):
            msg[BrokerConstants.TIMESTAMP_KEY] = (now + (i * td_30_mins)).isoformat()
            msg[BrokerConstants.LOGICAL_DEVICE_UID_KEY] = new_ldev.uid

        msg_list.sort(key=lambda m: m[BrokerConstants.TIMESTAMP_KEY], reverse=True)

        msg_ts.clear()
        for msg in msg_list:
            dao.insert_physical_timeseries_message(msg)
            msg_ts.append(dateutil.parser.isoparse(msg[BrokerConstants.TIMESTAMP_KEY]))

        # This will return a single message because 'end' is None, meaning the DAO will set the
        # end timestamp to 'now'. This batch of messages has timestamps from 1 minute ago to a
        # couple of hours in the future, so only the message with the earliest timestamp in the
        # batch should be returned.
        msgs = dao.get_physical_timeseries_message(only_timestamp=True, l_uid=new_ldev.uid)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0], msg_ts[-1])

        # This will return all the messages because 'end' has been set past the latest message timestamp.
        msgs = dao.get_physical_timeseries_message(end=now + datetime.timedelta(days=1), only_timestamp=True, l_uid=new_ldev.uid)
        self.assertEqual(len(msgs), len(msg_list))
        for i, ts in enumerate(msgs):
            self.assertEqual(ts, msg_ts[i])

        # Should return only the latest message.
        msgs = dao.get_physical_timeseries_message(end=now + datetime.timedelta(days=1), only_timestamp=True, count=1, l_uid=new_ldev.uid)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0], msg_ts[0])

        self.assertRaises(ValueError, dao.get_physical_timeseries_message)
        self.assertRaises(TypeError, dao.get_physical_timeseries_message, p_uid='x')
        self.assertRaises(TypeError, dao.get_physical_timeseries_message, l_uid='x')
        self.assertRaises(TypeError, dao.get_physical_timeseries_message, start='x', l_uid=1)
        self.assertRaises(TypeError, dao.get_physical_timeseries_message, end='x', l_uid=1)
        self.assertRaises(TypeError, dao.get_physical_timeseries_message, count='x', l_uid=1)


    def test_add_raw_text_message(self):
        uuid1 = uuid.uuid4()
        msg1 = 'This is a text message.'
        dao.add_raw_text_message('greenbrain', _now(), uuid1, msg1)

        uuid2 = uuid.uuid4()
        msg2 = 'This is a text message 2.'
        dao.add_raw_text_message('greenbrain', _now(), uuid2, msg2, 2)
        with dao._get_connection() as conn, conn.cursor() as cursor:
            cursor.execute('select physical_uid, correlation_id, text_msg from raw_messages')
            self.assertEqual(2, cursor.rowcount)

            p_uid, c_id, msg = cursor.fetchone()
            self.assertIsNone(p_uid)
            self.assertEqual(c_id, uuid1)
            self.assertEqual(msg, msg)

            p_uid, c_id, msg = cursor.fetchone()
            self.assertEqual(p_uid, 2)
            self.assertEqual(c_id, uuid2)
            self.assertEqual(msg, msg2)

        # Confirm the DAO raises a warning when trying to add a message with a
        # duplicate UUID, but doesn't throw an exception.
        with self.assertWarns(UserWarning):
            dao.add_raw_text_message('ttn', _now(), uuid1, msg1)

    def test_user_add(self):
        uname = _create_test_user()
        users = dao.user_ls()

        self.assertEqual(uname, users[-1])

    def test_user_rm(self):
        uname = _create_test_user()
        dao.user_rm(uname)
        self.assertFalse(uname in dao.user_ls())

    def test_user_set_read_only(self):
        uname= _create_test_user()
        dao.user_set_read_only(uname, False)
        user_token=dao.user_get_token(username=uname, password='password')
        user=dao.get_user(auth_token=user_token)
        self.assertFalse(user.read_only)

    def test_add_non_unique_user(self):
        #Check that two users with the same username cannot be created
        uname = _create_test_user()
        self.assertRaises(dao.DAOUniqeConstraintException, dao.user_add, uname, 'password', False)
    
    def test_get_user_token(self):
        uname = _create_test_user()
        self.assertIsNotNone(dao.user_get_token(username=uname, password='password'))
        self.assertIsNone(dao.user_get_token(username=uname, password='x'))

    def test_user_token_refresh(self):
        uname = _create_test_user()
        token1 = dao.user_get_token(username=uname, password='password')
        dao.token_refresh(uname=uname)
        token2 = dao.user_get_token(username=uname, password='password')

        self.assertNotEqual(token1, token2)

    def test_user_token_disable(self):
        uname = _create_test_user()
        user_token = dao.user_get_token(username=uname, password='password')
        
        dao.token_disable(uname)
        self.assertFalse(dao.token_is_valid(user_token))
        
    def test_user_token_enable(self):
        uname = _create_test_user()
        user_token = dao.user_get_token(username=uname, password='password')
        
        dao.token_disable(uname)
        dao.token_enable(uname)
        self.assertTrue(dao.token_is_valid(user_token))
        
    def test_user_change_password(self):
        uname = _create_test_user()
        dao.user_change_password(uname, 'nuiscyeriygsreiuliu')
        self.assertIsNotNone(dao.user_get_token(username=uname, password='nuiscyeriygsreiuliu'))


if __name__ == '__main__':
    unittest.main()
