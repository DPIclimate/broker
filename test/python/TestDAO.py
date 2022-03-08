import copy, datetime, logging, time, unittest, uuid
from typing import Tuple

import api.client.DAO as dao
from pdmodels.Models import PhysicalDevice, PhysicalToLogicalMapping, Location, LogicalDevice
from typing import Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
logger = logging.getLogger(__name__)
logging.captureWarnings(True)

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

    def test_get_all_physical_sources(self):
        sources = dao.get_all_physical_sources()
        self.assertEqual(sources, ['greenbrain', 'ttn'])

    def now(self):
        return datetime.datetime.now(tz=datetime.timezone.utc)

    def _create_default_physical_device(self) -> Tuple[PhysicalDevice, PhysicalDevice]:
        last_seen = self.now()
        dev = PhysicalDevice(source_name='ttn', name='Test Device', location=Location(lat=3, long=-31), last_seen=last_seen,
            source_ids={'appId': 'x', 'devId': 'y'},
            properties={'appId': 'x', 'devId': 'y', 'other': 'z'})
        return (dev, dao.create_physical_device(dev))

    def test_create_physical_device(self):
        dev, new_dev = self._create_default_physical_device()

        # Don't fail the equality assertion due to the uid being None in dev.
        dev.uid = new_dev.uid
        self.assertEqual(dev, new_dev)

    def test_get_physical_device(self):
        dev, new_dev = self._create_default_physical_device()

        got_dev = dao.get_physical_device(new_dev.uid)
        self.assertEqual(new_dev, got_dev)

        dev = dao.get_physical_device(-1)
        self.assertIsNone(dev)

    def test_get_physical_device_using_source_ids(self):
        dev, new_dev = self._create_default_physical_device()

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
        dev, new_dev = self._create_default_physical_device()

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
        dev, new_dev = self._create_default_physical_device()
        self.assertEqual(dao.delete_physical_device(new_dev.uid), new_dev)

        # Confirm the device was deleted.
        self.assertIsNone(dao.get_physical_device(new_dev.uid))

        # Confirm delete does not throw an exception when the device does not exist.
        self.assertIsNone(dao.delete_physical_device(new_dev.uid))

    def test_create_physical_device_note(self):
        dev, new_dev = self._create_default_physical_device()
        dao.create_physical_device_note(new_dev.uid, 'Note 1')
        dao.create_physical_device_note(new_dev.uid, 'Note 2')

        self.assertRaises(dao.DAODeviceNotFound, dao.create_physical_device_note, -1, 'Note 1')

    def test_get_physical_device_notes(self):
        dev, new_dev = self._create_default_physical_device()
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

    def _create_default_logical_device(self) -> Tuple[LogicalDevice, LogicalDevice]:
        last_seen = self.now()
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
        pdev, new_pdev = self._create_default_physical_device()
        ldev, new_ldev = self._create_default_logical_device()
        mapping = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=self.now())

        # This should work.
        dao.insert_mapping(mapping)

        # This should fail due to duplicate start time.
        self.assertRaises(dao.DAOException, dao.insert_mapping, mapping)

        time.sleep(0.001)
        mapping.start_time=self.now()
        dao.insert_mapping(mapping)

        pdx = copy.deepcopy(new_pdev)
        pdx.uid = -1
        mapping = PhysicalToLogicalMapping(pd=pdx, ld=new_ldev, start_time=self.now())
        # This should fail due to invalid physical uid.
        self.assertRaises(dao.DAODeviceNotFound, dao.insert_mapping, mapping)

        ldx = copy.deepcopy(new_ldev)
        ldx.uid = -1
        mapping = PhysicalToLogicalMapping(pd=new_pdev, ld=ldx, start_time=self.now())
        # This should fail due to invalid logical uid.
        self.assertRaises(dao.DAODeviceNotFound, dao.insert_mapping, mapping)

    def test_get_current_device_mapping(self):
        pdev, new_pdev = self._create_default_physical_device()
        ldev, new_ldev = self._create_default_logical_device()

        # No mapping yet, confirm all forms of call return None.
        self.assertIsNone(dao.get_current_device_mapping(pd=-1))
        self.assertIsNone(dao.get_current_device_mapping(pd=new_pdev))

        self.assertIsNone(dao.get_current_device_mapping(ld=-1))
        self.assertIsNone(dao.get_current_device_mapping(ld=new_ldev))

        # Confirm pd or ld must be given.
        self.assertRaises(dao.DAOException, dao.get_current_device_mapping)

        # Confirm only pd or ld can be given.
        self.assertRaises(dao.DAOException, dao.get_current_device_mapping, -1, -1)
        self.assertRaises(dao.DAOException, dao.get_current_device_mapping, new_pdev, new_ldev)

        # confirm a physical device can be mapped to a logical device.        
        mapping1 = PhysicalToLogicalMapping(pd=new_pdev, ld=new_ldev, start_time=self.now())
        dao.insert_mapping(mapping1)

        self.assertEqual(mapping1, dao.get_current_device_mapping(pd=new_pdev.uid))
        self.assertEqual(mapping1, dao.get_current_device_mapping(pd=new_pdev))
        self.assertEqual(mapping1, dao.get_current_device_mapping(ld=new_ldev.uid))
        self.assertEqual(mapping1, dao.get_current_device_mapping(ld=new_ldev))

        # Confirm mapping a new physical device to the same logical device overrides the
        # original mapping.
        time.sleep(0.001)
        pdev2, new_pdev2 = self._create_default_physical_device()

        mapping2 = PhysicalToLogicalMapping(pd=new_pdev2, ld=new_ldev, start_time=self.now())
        dao.insert_mapping(mapping2)

        self.assertEqual(mapping2, dao.get_current_device_mapping(pd=new_pdev2.uid))
        self.assertEqual(mapping2, dao.get_current_device_mapping(pd=new_pdev2))
        self.assertEqual(mapping2, dao.get_current_device_mapping(ld=new_ldev.uid))
        self.assertEqual(mapping2, dao.get_current_device_mapping(ld=new_ldev))

    def test_add_raw_json_message(self):
        uuid1 = uuid.uuid4()
        obj1 = {'a':1, 'b':'2', 'c':True, 'd':False}
        dao.add_raw_json_message('ttn', self.now(), uuid1, obj1)

        uuid2 = uuid.uuid4()
        obj2 = {'a':1, 'b':'2', 'c':False, 'd':True}
        dao.add_raw_json_message('ttn', self.now(), uuid2, obj2, 1)

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
            dao.add_raw_json_message('ttn', self.now(), uuid1, obj1)

    def test_add_raw_text_message(self):
        uuid1 = uuid.uuid4()
        msg1 = 'This is a text message.'
        dao.add_raw_text_message('greenbrain', self.now(), uuid1, msg1)

        uuid2 = uuid.uuid4()
        msg2 = 'This is a text message 2.'
        dao.add_raw_text_message('greenbrain', self.now(), uuid2, msg2, 2)
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
            dao.add_raw_text_message('ttn', self.now(), uuid1, msg1)

if __name__ == '__main__':
    unittest.main()
