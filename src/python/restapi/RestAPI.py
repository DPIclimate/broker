from fastapi import FastAPI, Query, HTTPException, status
import json
from typing import Dict, List, Optional

from pdmodels.Models import PhysicalDevice
import db.DAO as dao

app = FastAPI()


@app.get("/api/physical/sources/")
async def get_all_physical_sources() -> List[str]:
    return dao.get_all_physical_sources()


@app.get("/api/physical/devices/")
async def query_physical_devices(source: Optional[str] = None, prop_name: Optional[List[str]] = Query(None), prop_value: Optional[List[str]] = Query(None)) -> List[PhysicalDevice]:
    """
    Query PhysicalDevices. The query parameters are:

    source: should be one of the device sources such as ttn or mace.

    prop_name and prop_value: pairs of query parameters that work together such as
    prop_name=deveui&prop_value=01eeddcc44532312. For multiple properties, give both
    parameters multiple times, such as prop_name=a&prop_value=b&prop_name=i&prop_value=j.
    """

    # locals() returns a dict of the local variables. In this case it's like kwargs which is what the
    # dao.get_physical_devices() function is expecting. If any local variables are declared in this
    # function then they will also be passed in but that's probably ok.
    return dao.get_physical_devices(locals())


@app.get("/api/physical/devices/{uid}")
async def get_physical_device(uid: int) -> PhysicalDevice:
    """
    Get the PhysicalDevice specified by uid.
    """
    dev = dao.get_physical_device(uid)
    if dev is None:
        raise HTTPException(status_code=404, detail="Physical device not found")

    return dev


@app.post("/api/physical/devices/", status_code=status.HTTP_201_CREATED)
async def create_physical_device(device: PhysicalDevice) -> PhysicalDevice:
    """
    Create a new PhysicalDevice. The new device is returned in the response.
    """
    return dao.create_physical_device(device)


@app.patch("/api/physical/devices/{uid}")
async def update_physical_device(uid: int, device: PhysicalDevice) -> PhysicalDevice:
    """
    Update a PhysicalDevice. The updated device is returned in the respose.
    """
    try:
        updated_device = dao.update_physical_device(uid, device)
    except dao.DAOException:
        raise HTTPException(status_code=404, detail="Physical device not found")

    return updated_device


@app.delete("/api/physical/devices/{uid}")
async def delete_physical_device(uid: int) -> PhysicalDevice:
    """
    Delete a PhysicalDevice. The deleted device is returned in the response.
    """
    try:
        dev = dao.delete_physical_device(uid)
    except dao.DAOException:
        raise HTTPException(status_code=404)

    return dev
