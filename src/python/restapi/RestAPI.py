#
# TODO:
#
# Test the behaviour of all calls when the DB is down. Ensure they return sensible
# status codes.
#

from fastapi import APIRouter, FastAPI, Query, HTTPException, Request, Response, status
from typing import Dict, List

from pdmodels.Models import DeviceNote, PhysicalDevice, LogicalDevice, PhysicalToLogicalMapping
import api.client.DAO as dao

import util.LoggingUtil as lu
import logging

router = APIRouter(prefix='/broker/api')

"""
An example of how we might do not-very-good authentication for the
REST API. The point is, it is simple to wrap every call with a
function to check the caller credentials.

auth_token = os.getenv('RESTAPI_TOKEN')
if auth_token is None or len(auth_token) < 1:
    logger.error('auth_token not set.')
    sys.exit(1)

@router.middleware("http")
async def check_auth_header(request: Request, call_next):
    if not 'X-Auth-Token' in request.headers:
        return JSONResponse(status_code=401)

    token = request.headers['X-Auth-Token']
    if token != auth_token:
        return JSONResponse(status_code=401)

    return await call_next(request)
"""

@router.get("/physical/sources/", tags=['physical devices'])
async def get_all_physical_sources() -> List[str]:
    """
    Return a list of all physical device sources.
    """
    try:
        return dao.get_all_physical_sources()
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.get("/physical/devices/", tags=['physical devices'])
async def query_physical_devices(source_name: str = None) -> List[PhysicalDevice]:
    """
    Query PhysicalDevices.
    """

    # locals() returns a dict of the local variables. In this case it's like kwargs which is what the
    # dao.get_physical_devices() function is expecting. If any local variables are declared in this
    # function then they will also be passed in but that's probably ok.
    #return dao.get_physical_devices(locals())

    devs: List[PhysicalDevice] = []
    
    """
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
    """

    if source_name is None:
        devs = dao.get_all_physical_devices()
    else:
        devs = dao.get_physical_devices_from_source(source_name)
    return devs


@router.get("/physical/devices/{uid}", tags=['physical devices'])
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


@router.get("/physical/devices/unmapped/", tags=['physical devices'])
async def get_unmapped_physical_devices() -> List[PhysicalDevice]:
    """
    Returns a list of unmapped PhysicalDevices.
    """
    try:
        return dao.get_unmapped_physical_devices()
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.post("/physical/devices/", tags=['physical devices'], status_code=status.HTTP_201_CREATED)
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


@router.patch("/physical/devices/", tags=['physical devices'])
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


@router.delete("/physical/devices/{uid}", tags=['physical devices'])
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
@router.post("/physical/devices/notes/{uid}", tags=['physical devices'], status_code=status.HTTP_201_CREATED)
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


@router.get("/physical/devices/notes/{uid}", tags=['physical devices'])
async def get_physical_device_notes(uid: int) -> List[DeviceNote]:
    try:
        return dao.get_physical_device_notes(uid)
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)

"""--------------------------------------------------------------------------
LOGICAL DEVICES
--------------------------------------------------------------------------"""

@router.post("/logical/devices/", tags=['logical devices'], status_code=status.HTTP_201_CREATED)
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


@router.get("/logical/devices/", tags=['logical devices'])
async def get_logical_devices() -> LogicalDevice:
    """
    Get all LogicalDevices.
    """
    try:
        devs = dao.get_logical_devices()
        return devs
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.get("/logical/devices/{uid}", tags=['logical devices'])
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


@router.patch("/logical/devices/", tags=['logical devices'])
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


@router.delete("/logical/devices/{uid}", tags=['logical devices'])
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

@router.post("/mappings/", tags=['device mapping'], status_code=status.HTTP_201_CREATED)
async def insert_mapping(mapping: PhysicalToLogicalMapping) -> None:
    try:
        dao.insert_mapping(mapping)
    except dao.DAODeviceNotFound as daonf:
        raise HTTPException(status_code=404, detail=daonf.msg)
    except dao.DAOUniqeConstraintException as err:
        raise HTTPException(status_code=400, detail=err.msg)
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.get("/mappings/physical/current/{uid}", tags=['device mapping'], response_model=PhysicalToLogicalMapping)
async def get_mapping_from_physical_uid(uid: int) -> PhysicalToLogicalMapping:
    try:
        mapping = dao.get_current_device_mapping(pd=uid)
        if mapping is None:
            raise HTTPException(status_code=404, detail=f'Device mapping for physical device {uid} not found.')

        return mapping
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.patch("/mappings/physical/end/{uid}", tags=['device mapping'], status_code=status.HTTP_204_NO_CONTENT)
async def end_mapping_of_physical_uid(uid: int) -> None:
    try:
        mapping = dao.get_current_device_mapping(pd=uid)
        if mapping is None:
            raise HTTPException(status_code=404, detail=f'Device mapping for physical device {uid} not found.')

        dao.end_mapping(pd=uid)
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.get("/mappings/logical/current/{uid}", tags=['device mapping'], response_model=PhysicalToLogicalMapping)
async def get_mapping_from_logical_uid(uid: int) -> PhysicalToLogicalMapping:
    try:
        mapping = dao.get_current_device_mapping(ld=uid)
        if mapping is None:
            raise HTTPException(status_code=404, detail=f'Device mapping for logical device {uid} not found.')

        return mapping
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.patch("/mappings/logical/end/{uid}", tags=['device mapping'], status_code=status.HTTP_204_NO_CONTENT)
async def end_mapping_of_logical_uid(uid: int) -> None:
    try:
        mapping = dao.get_current_device_mapping(ld=uid)
        if mapping is None:
            raise HTTPException(status_code=404, detail=f'Device mapping for logical device {uid} not found.')

        dao.end_mapping(ld=uid)
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


app = FastAPI(title='IoT Device Broker', version='1.0.0')
app.include_router(router)
