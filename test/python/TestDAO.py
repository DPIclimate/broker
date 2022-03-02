import datetime, unittest

import db.DAO as dao
from pdmodels.Models import PhysicalDevice, Location

class TestDAO(unittest.TestCase):

    def setUp(self):
        try:
            with dao._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('truncate physical_logical_map')
                    cursor.execute('truncate physical_devices cascade')
                    cursor.execute('truncate logical_devices cascade')
        finally:
            dao.free_conn(conn)

    def test_get_all_physical_sources(self):
        sources = dao.get_all_physical_sources()
        self.assertEqual(sources, ['greenbrain', 'ttn'])

    def test_get_missing_physical_device(self):
        dev = dao.get_physical_device(1)
        self.assertIsNone(dev)

    def test_create_physical_device(self):
        last_seen = datetime.datetime.now(tz=datetime.timezone.utc)
        dev = PhysicalDevice(source_name='ttn', name='Test Device', location=Location(lat=3, long=-31), last_seen=last_seen,
            source_ids={'appId': 'x', 'devId': 'y'},
            properties={'appId': 'x', 'devId': 'y', 'other': 'z'})

        new_dev = dao.create_physical_device(dev)

        # Don't fail the equality assertion due to the uid being None in dev.
        dev.uid = new_dev.uid
        self.assertEqual(dev, new_dev)

    def test_get_physical_device(self):
        last_seen = datetime.datetime.now(tz=datetime.timezone.utc)
        dev = PhysicalDevice(source_name='ttn', name='Test Device', location=Location(lat=3, long=-31), last_seen=last_seen,
            source_ids={'appId': 'x', 'devId': 'y'},
            properties={'appId': 'x', 'devId': 'y', 'other': 'z'})

        new_dev = dao.create_physical_device(dev)

        got_dev = dao.get_physical_device(new_dev.uid)
        self.assertEqual(new_dev, got_dev)

    def test_get_physical_device_using_source_ids(self):
        last_seen = datetime.datetime.now(tz=datetime.timezone.utc)
        dev = PhysicalDevice(source_name='ttn', name='Test Device', location=Location(lat=3, long=-31), last_seen=last_seen,
            source_ids={'appId': 'x', 'devId': 'y'},
            properties={'appId': 'x', 'devId': 'y', 'other': 'z'})

        new_dev = dao.create_physical_device(dev)

        # Create an otherwise similar device from a different source to verify
        # the source_name is taken into account by the dao method.
        dev.source_name = 'greenbrain'
        dao.create_physical_device(dev)

        got_dev = dao.get_pyhsical_device_using_source_ids('ttn', {'appId': 'x'})
        self.assertEqual(new_dev, got_dev)

        got_dev = dao.get_pyhsical_device_using_source_ids('ttn', {'devId': 'y'})
        self.assertEqual(new_dev, got_dev)

        got_dev = dao.get_pyhsical_device_using_source_ids('ttn', {'devId': 'x'})
        self.assertIsNone(got_dev)

    def test_update_physical_device(self):
        last_seen = datetime.datetime.now(tz=datetime.timezone.utc)
        dev = PhysicalDevice(source_name='ttn', name='Test Device', location=Location(lat=3, long=-31), last_seen=last_seen,
            source_ids={'appId': 'x', 'devId': 'y'},
            properties={'appId': 'x', 'devId': 'y', 'other': 'z'})

        new_dev = dao.create_physical_device(dev)

        new_dev.name = 'X'
        updated_dev = dao.update_physical_device(new_dev.uid, new_dev)
        self.assertEqual(updated_dev, new_dev)

    def test_delete_physical_device(self):
        last_seen = datetime.datetime.now(tz=datetime.timezone.utc)
        dev = PhysicalDevice(source_name='ttn', name='Test Device', location=Location(lat=3, long=-31), last_seen=last_seen,
            source_ids={'appId': 'x', 'devId': 'y'},
            properties={'appId': 'x', 'devId': 'y', 'other': 'z'})

        new_dev = dao.create_physical_device(dev)
        self.assertEqual(dao.delete_physical_device(new_dev.uid), new_dev)
        self.assertIsNone(dao.get_physical_device(new_dev.uid))

if __name__ == '__main__':
    unittest.main()
