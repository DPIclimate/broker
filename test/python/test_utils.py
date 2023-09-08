import datetime
import os
import api.client.DAO as dao
from pdmodels.Models import DeviceNote, PhysicalDevice, PhysicalToLogicalMapping, Location, LogicalDevice, User


def create_test_user() -> User:
    test_uname = os.urandom(4).hex()
    dao.user_add(uname=test_uname, passwd='password', disabled=False)
    user = dao.get_user(username=test_uname)
    return user


def now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)
