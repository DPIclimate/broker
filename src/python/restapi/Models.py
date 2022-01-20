from datetime import datetime, tzinfo, timezone, timedelta, date
from pydantic import BaseModel
from typing import Optional, Dict, Tuple

class Location(BaseModel):
    lat: float
    long: float

"""
create table if not exists physical_devices (
    uid integer generated always as identity primary key,
    source_name text not null references sources,
    name text not null,
    location point,
    last_seen timestamptz,
    properties jsonb not null default '{}'
);

"""
class PhysicalDevice(BaseModel):
    uid: Optional[int]
    source_name: str
    name: str
    location: Optional[Location]
    last_seen: Optional[datetime]
    properties = {}
