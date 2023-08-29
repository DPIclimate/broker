from datetime import datetime, timezone
from optparse import Option
from pydantic import BaseModel
from typing import Optional, Dict

class Location(BaseModel):
    lat: float
    long: float

    @staticmethod
    def from_ttn_device(ttn_dev: Dict):
        dev_loc = None

        if 'locations' in ttn_dev and 'user' in ttn_dev['locations']:
            user_loc = ttn_dev['locations']['user']
            dev_lat = user_loc['latitude']
            dev_long = user_loc['longitude']
            dev_loc = Location(lat=dev_lat, long=dev_long)

        return dev_loc


class PhysicalDevice(BaseModel):
    uid: Optional[int]
    source_name: str
    name: str
    location: Optional[Location]
    last_seen: Optional[datetime]
    source_ids: Dict = {}
    properties: Dict = {}


class LogicalDevice(BaseModel):
    uid: Optional[int]
    name: str
    location: Optional[Location]
    last_seen: Optional[datetime]
    properties = {}


class PhysicalToLogicalMapping(BaseModel):
    pd: PhysicalDevice | int
    ld: LogicalDevice | int
    start_time: datetime
    end_time: Optional[datetime]
    is_active: bool = True


class DeviceNote(BaseModel):
    uid: Optional[int]
    ts: Optional[datetime]
    note: str


class User(BaseModel):
    uid: int
    username: str
    auth_token: str
    valid: bool
    read_only: bool