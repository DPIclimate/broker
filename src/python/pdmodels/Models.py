from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict


class Location(BaseModel):
    lat: Optional[float] = None
    long: Optional[float] = None

    @staticmethod
    def from_ttn_device(ttn_dev: Dict):
        dev_loc = None

        if 'locations' in ttn_dev and 'user' in ttn_dev['locations']:
            user_loc = ttn_dev['locations']['user']
            dev_lat = user_loc['latitude']
            dev_long = user_loc['longitude']
            dev_loc = Location(lat=dev_lat, long=dev_long)

        return dev_loc


# Allowing extra attributes in this class to make life easier for the webapp - it can pass extra info
# to the templates in the device object rather than passing in lists of mappings etc.
class BaseDevice(BaseModel):
    model_config = ConfigDict(extra='allow')

    uid: Optional[int] = None
    name: str
    location: Optional[Location] = None
    last_seen: Optional[datetime] = None
    properties: Dict = Field(default_factory=dict)


# Allowing extra attributes in this class to make life easier for the webapp - it can pass extra info
# to the templates in the device object rather than passing in lists of mappings etc.
class PhysicalDevice(BaseDevice):
    source_name: str
    source_ids: Dict = Field(default_factory=dict)


# Allowing extra attributes in this class to make life easier for the webapp - it can pass extra info
# to the templates in the device object rather than passing in lists of mappings etc.
class LogicalDevice(BaseDevice):
    pass


class PhysicalToLogicalMapping(BaseModel):
    pd: PhysicalDevice | int
    ld: LogicalDevice | int
    start_time: datetime
    end_time: Optional[datetime] = None
    is_active: bool = True


class DeviceNote(BaseModel):
    uid: Optional[int] = None
    ts: Optional[datetime] = None
    note: str


class User(BaseModel):
    uid: int
    username: str
    auth_token: str
    valid: bool
    read_only: bool
