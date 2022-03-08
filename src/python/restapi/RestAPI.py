#
# TODO:
#
# Test the behaviour of all calls when the DB is down. Ensure they return sensible
# status codes.
#

from fastapi import FastAPI, Query, HTTPException, Request, Response, status
import json
from typing import Dict, List, Optional

from pdmodels.Models import DeviceNote, PhysicalDevice, LogicalDevice, PhysicalToLogicalMapping
import api.client.DAO as dao

app = FastAPI()


@app.get("/api/physical/sources/")
async def get_all_physical_sources() -> List[str]:
    """
    Return a list of all physical device sources.
    """
    try:
        return dao.get_all_physical_sources()
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@app.get("/api/physical/devices/")
async def query_physical_devices(
    source: str | None = None,
    source_id_name: List[str] | None = Query(None),
    source_id_value: List[str] | None = Query(None)) -> List[PhysicalDevice]:
    """
    Query PhysicalDevices. The query parameters are:

    source: should be one of the device sources such as ttn or mace.
    """

    # locals() returns a dict of the local variables. In this case it's like kwargs which is what the
    # dao.get_physical_devices() function is expecting. If any local variables are declared in this
    # function then they will also be passed in but that's probably ok.
    #return dao.get_physical_devices(locals())

    devs: List[PhysicalDevice] = []

    if source is not None and source_id_name is not None and source_id_value is not None:
        source_ids: Dict[str, str] = {}
        s_names: List[str] = []
        s_values: List[str] = []

        # Unpack comma separated names & values in the query paramaters.
        for ks, vs in zip(source_id_name, source_id_value):
            s_names.extend(ks.split(','))
            s_values.extend(vs.split(','))

        # Transform into a dict
        for k, v in zip(s_names, s_values):
            source_ids[k] = v

        devs = dao.get_pyhsical_devices_using_source_ids(source, source_ids)

    return devs



@app.get("/api/physical/devices/{uid}")
async def get_physical_device(uid: int) -> PhysicalDevice:
    """
    Get the PhysicalDevice specified by uid.
    """
    try:
        dev = dao.get_physical_device(uid)
        if dev is None:
            raise HTTPException(status_code=404, detail="Physical device not found")

        return dev
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@app.post("/api/physical/devices/", status_code=status.HTTP_201_CREATED)
async def create_physical_device(device: PhysicalDevice, request: Request, response: Response) -> PhysicalDevice:
    """
    Create a new PhysicalDevice. The new device is returned in the response.
    """
    try:
        pd = dao.create_physical_device(device)
        response.headers['Location'] = f'{request.url}{pd.uid}'
        return pd
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@app.patch("/api/physical/devices/")
async def update_physical_device(device: PhysicalDevice) -> PhysicalDevice:
    """
    Update a PhysicalDevice. The updated device is returned in the respose.
    """
    try:
        return dao.update_physical_device(device)
    except dao.DAODeviceNotFound as daonf:
        raise HTTPException(status_code=404, detail=daonf.msg)
    except dao.DAOException as err:
        print(err)
        raise HTTPException(status_code=500, detail=err.msg)



@app.delete("/api/physical/devices/{uid}")
async def delete_physical_device(uid: int) -> PhysicalDevice:
    """
    Delete a PhysicalDevice. The deleted device is returned in the response.
    """
    try:
        return dao.delete_physical_device(uid)
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


"""--------------------------------------------------------------------------
DEVICE NOTES
--------------------------------------------------------------------------"""
@app.post("/api/physical/devices/notes/{uid}", status_code=status.HTTP_201_CREATED)
async def create_physical_device_note(uid: int, note: DeviceNote, request: Request, response: Response) -> None:
    """
    Create a new note for a PhysicalDevice.
    """
    try:
        dao.create_physical_device_note(uid, note.note)
        #response.headers['Location'] = f'{request.url}{pd.uid}'
    except dao.DAODeviceNotFound as err:
        raise HTTPException(status_code=404, detail=err.msg)
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@app.get("/api/physical/devices/notes/{uid}")
async def get_physical_device_notes(uid: int) -> List[DeviceNote]:
    try:
        return dao.get_physical_device_notes(uid)
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)

"""--------------------------------------------------------------------------
LOGICAL DEVICES
--------------------------------------------------------------------------"""

@app.post("/api/logical/devices/", status_code=status.HTTP_201_CREATED)
async def create_logical_device(device: LogicalDevice, request: Request, response: Response) -> LogicalDevice:
    """
    Create a new LogicalDevice. The new device is returned in the response.
    """
    try:
        ld = dao.create_logical_device(device)
        response.headers['Location'] = f'{request.url}{ld.uid}'
        return ld
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@app.get("/api/logical/devices/{uid}")
async def get_logical_device(uid: int) -> LogicalDevice:
    """
    Get the LogicalDevice specified by uid.
    """
    try:
        dev = dao.get_logical_device(uid)
        if dev is None:
            raise HTTPException(status_code=404, detail="Logical device not found")

        return dev
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@app.patch("/api/logical/devices/")
async def update_logical_device(device: LogicalDevice) -> LogicalDevice:
    """
    Update a LogicalDevice. The updated device is returned in the respose.
    """
    try:
        return dao.update_logical_device(device)
    except dao.DAODeviceNotFound as daonf:
        raise HTTPException(status_code=404, detail=daonf.msg)
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@app.delete("/api/logical/devices/{uid}")
async def delete_logical_device(uid: int) -> LogicalDevice:
    """
    Delete a LogicalDevice. The deleted device is returned in the response.
    """
    try:
        return dao.delete_logical_device(uid)
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


"""--------------------------------------------------------------------------
DEVICE MAPPINGS
--------------------------------------------------------------------------"""

@app.post("/api/mappings/", status_code=status.HTTP_201_CREATED)
async def insert_mapping(mapping: PhysicalToLogicalMapping) -> None:
    try:
        dao.insert_mapping(mapping)
    except dao.DAODeviceNotFound as daonf:
        raise HTTPException(status_code=404, detail=daonf.msg)
    except dao.DAOUniqeConstraintException as err:
        raise HTTPException(status_code=400, detail=err.msg)
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)

@app.get("/api/mappings/from_physical/{uid}")
async def get_mapping_from_physical_uid(uid: int) -> PhysicalToLogicalMapping:
    try:
        mapping = dao.get_current_device_mapping(pd=uid)
        if mapping is None:
            raise HTTPException(status_code=404, detail=f'Device mapping for physical device {uid} not found.')

        return mapping
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)

@app.get("/api/mappings/from_logical/{uid}")
async def get_mapping_from_logical_uid(uid: int) -> PhysicalToLogicalMapping:
    try:
        mapping = dao.get_current_device_mapping(ld=uid)
        if mapping is None:
            raise HTTPException(status_code=404, detail=f'Device mapping for logical device {uid} not found.')

        return mapping
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)
