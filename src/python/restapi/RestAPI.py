#
# TODO:
#
# Test the behaviour of all calls when the DB is down. Ensure they return sensible
# status codes.
#

import datetime
import json
import logging

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, status, Query
from fastapi.security import HTTPBearer, HTTPBasic

#from fastapi.responses import JSONResponse
from typing import Annotated, List, Dict

from pdmodels.Models import DeviceNote, PhysicalDevice, LogicalDevice, PhysicalToLogicalMapping
import api.client.DAO as dao

import base64

# Scheme for the Authorization header
token_auth_scheme = HTTPBearer()
http_basic_auth = HTTPBasic()

# router = APIRouter(prefix='/broker/api', dependencies=[Depends(token_auth_scheme)])
router = APIRouter(prefix='/broker/api')

@router.get("/physical/sources/", tags=['physical devices'], dependencies=[Depends(token_auth_scheme)])
async def get_all_physical_sources() -> List[str]:
    """
    Return a list of all physical device sources.
    """
    try:
        return dao.get_all_physical_sources()
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.get("/physical/devices/", tags=['physical devices'], dependencies=[Depends(token_auth_scheme)])
async def query_physical_devices(source_name: str = None, include_properties: bool | None = True) -> List[PhysicalDevice]:
    """
    Returns a list of PhysicalDevices.

    If the `source_name` query parameter is given, only devices from that source are returned.
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

    if include_properties != True:
        for d in devs:
            d.properties = {}

    return devs


@router.get("/physical/devices/{uid}", tags=['physical devices'], dependencies=[Depends(token_auth_scheme)])
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


@router.get("/physical/devices/unmapped/", tags=['physical devices'], dependencies=[Depends(token_auth_scheme)])
async def get_unmapped_physical_devices() -> List[PhysicalDevice]:
    """
    Returns a list of unmapped PhysicalDevices.
    """
    try:
        return dao.get_unmapped_physical_devices()
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.post("/physical/devices/", tags=['physical devices'], status_code=status.HTTP_201_CREATED, dependencies=[Depends(token_auth_scheme)])
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


@router.patch("/physical/devices/", tags=['physical devices'], dependencies=[Depends(token_auth_scheme)])
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


@router.delete("/physical/devices/{uid}", tags=['physical devices'], status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(token_auth_scheme)])
async def delete_physical_device(uid: int) -> None:
    """
    Delete a PhysicalDevice. The deleted device is returned in the response.
    """
    try:
        pd = dao.delete_physical_device(uid)
        if pd is None:
            raise HTTPException(status_code=404)

    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


"""--------------------------------------------------------------------------
DEVICE NOTES
--------------------------------------------------------------------------"""
@router.post("/physical/devices/notes/{uid}", tags=['physical devices'], status_code=status.HTTP_201_CREATED, dependencies=[Depends(token_auth_scheme)])
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


@router.get("/physical/devices/notes/{uid}", tags=['physical devices'], dependencies=[Depends(token_auth_scheme)])
async def get_physical_device_notes(uid: int) -> List[DeviceNote]:
    try:
        return dao.get_physical_device_notes(uid)
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.patch("/physical/devices/notes/", tags=['physical devices'], dependencies=[Depends(token_auth_scheme)])
async def patch_physical_device_note(note: DeviceNote) -> None:
    try:
        dao.update_physical_device_note(note)
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.delete("/physical/devices/notes/{uid}", tags=['physical devices'], status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(token_auth_scheme)])
async def delete_physical_device_note(uid: int) -> None:
    """
    Delete the given device note.
    """
    try:
        dao.delete_physical_device_note(uid)
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)

"""--------------------------------------------------------------------------
LOGICAL DEVICES
--------------------------------------------------------------------------"""

@router.post("/logical/devices/", tags=['logical devices'], status_code=status.HTTP_201_CREATED, dependencies=[Depends(token_auth_scheme)])
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


@router.get("/logical/devices/", tags=['logical devices'], dependencies=[Depends(token_auth_scheme)])
async def get_logical_devices(include_properties: bool | None = True) -> List[LogicalDevice]:
    """
    Get all LogicalDevices.
    """
    try:
        devs = dao.get_logical_devices()

        if include_properties != True:
            for d in devs:
                d.properties = {}

        return devs
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.get("/logical/devices/{uid}", tags=['logical devices'], dependencies=[Depends(token_auth_scheme)])
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


@router.patch("/logical/devices/", tags=['logical devices'], dependencies=[Depends(token_auth_scheme)])
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


@router.delete("/logical/devices/{uid}", tags=['logical devices'], status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(token_auth_scheme)])
async def delete_logical_device(uid: int) -> None:
    """
    Delete a LogicalDevice. The deleted device is returned in the response.
    """
    try:
        ld = dao.delete_logical_device(uid)
        if ld is None:
            raise HTTPException(status_code=404)
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


"""--------------------------------------------------------------------------
DEVICE MAPPINGS
--------------------------------------------------------------------------"""

@router.post("/mappings/", tags=['device mapping'], status_code=status.HTTP_201_CREATED, dependencies=[Depends(token_auth_scheme)])
async def insert_mapping(mapping: PhysicalToLogicalMapping) -> None:
    """
    Add the given physical to logical device mapping to the system. Messages from the
    physical device will be forwarded to the logical device.

    If the physical device is already mapped to a logical device, the call fails.

    If the logical device already has a mapping, that mapping is ended.
    """
    try:
        dao.insert_mapping(mapping)
    except dao.DAODeviceNotFound as daonf:
        raise HTTPException(status_code=404, detail=daonf.msg)
    except dao.DAOUniqeConstraintException as err:
        raise HTTPException(status_code=400, detail=err.msg)
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.get("/mappings/current/", tags=['device mapping'], response_model=List[PhysicalToLogicalMapping], dependencies=[Depends(token_auth_scheme)])
async def get_current_mappings(return_uids: bool = True) -> PhysicalToLogicalMapping:
    """
    Returns the _current_ mapping for all physical devices. A current mapping is one with no
    end time set, meaning messages from the physical device will be forwarded to the logical
    device.
    """
    try:
        mappings = dao.get_all_current_mappings(return_uids=return_uids)
        return mappings
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.get("/mappings/physical/current/{uid}", tags=['device mapping'], response_model=PhysicalToLogicalMapping, dependencies=[Depends(token_auth_scheme)])
async def get_current_mapping_from_physical_uid(uid: int) -> PhysicalToLogicalMapping:
    """
    Returns the _current_ mapping for the given physical device. A current mapping is one with no
    end time set, meaning messages from the physical device will be forwarded to the logical
    device.
    """
    try:
        mapping = dao.get_current_device_mapping(pd=uid)
        if mapping is None:
            raise HTTPException(status_code=404, detail=f'Device mapping for physical device {uid} not found.')

        return mapping
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.get("/mappings/physical/latest/{uid}", tags=['device mapping'], response_model=PhysicalToLogicalMapping, dependencies=[Depends(token_auth_scheme)])
async def get_latest_mapping_from_physical_uid(uid: int) -> PhysicalToLogicalMapping:
    """
    Returns the _latest_ mapping for the given physical device. The latest mapping is the most recent
    mapping for the logical device, even if it has ended.
    """
    try:
        mapping = dao.get_current_device_mapping(pd=uid, only_current_mapping=False)
        if mapping is None:
            raise HTTPException(status_code=404, detail=f'Device mapping for physical device {uid} not found.')

        return mapping
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.patch("/mappings/physical/end/{uid}", tags=['device mapping'], status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(token_auth_scheme)])
async def end_mapping_of_physical_uid(uid: int) -> None:
    """
    End the current mapping (if any) for the given physical device. This means messages will no longer
    be forwarded from this physical device. If there was a mapping, the logical device also has no mapping
    after this call.
    """
    try:
        mapping = dao.get_current_device_mapping(pd=uid)
        if mapping is None:
            raise HTTPException(status_code=404, detail=f'Device mapping for physical device {uid} not found.')

        dao.end_mapping(pd=uid)
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.get("/mappings/logical/current/{uid}", tags=['device mapping'], response_model=PhysicalToLogicalMapping, dependencies=[Depends(token_auth_scheme)])
async def get_current_mapping_to_logical_uid(uid: int) -> PhysicalToLogicalMapping:
    """
    Returns the _current_ mapping for the given logical device. A current mapping is one with no
    end time set, meaning messages from the physical device will be forwarded to the logical
    device.
    """
    try:
        mapping = dao.get_current_device_mapping(ld=uid)
        if mapping is None:
            raise HTTPException(status_code=404, detail=f'Device mapping for logical device {uid} not found.')

        return mapping
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.get("/mappings/logical/latest/{uid}", tags=['device mapping'], response_model=PhysicalToLogicalMapping, dependencies=[Depends(token_auth_scheme)])
async def get_latest_mapping_to_logical_uid(uid: int) -> PhysicalToLogicalMapping:
    """
    Returns the _latest_ mapping for the given logical device. The latest mapping is the most recent
    mapping for the logical device, even if it has ended.
    """
    try:
        mapping = dao.get_current_device_mapping(ld=uid, only_current_mapping=False)
        if mapping is None:
            raise HTTPException(status_code=404, detail=f'Device mapping for logical device {uid} not found.')

        return mapping
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.get("/mappings/logical/all/{uid}", tags=['device mapping'], dependencies=[Depends(token_auth_scheme)])
async def get_all_mappings_to_logical_uid(uid: int) -> List[PhysicalToLogicalMapping]:
    """
    Returns all mappings made to the given logical device.
    """
    try:
        mappings = dao.get_logical_device_mappings(ld=uid)
        if mappings is None:
            raise HTTPException(status_code=404, detail=f'No mappings to logical device {uid} were found.')

        return mappings
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


@router.patch("/mappings/logical/end/{uid}", tags=['device mapping'], status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(token_auth_scheme)])
async def end_mapping_of_logical_uid(uid: int) -> None:
    """
    End the current mapping (if any) for the given logical device. This means messages will no longer
    be forwarded to this logical device. If there was a mapping, the physical device also has no mapping
    after this call.
    """
    try:
        mapping = dao.get_current_device_mapping(ld=uid)
        if mapping is None:
            raise HTTPException(status_code=404, detail=f'Device mapping for logical device {uid} not found.')

        dao.end_mapping(ld=uid)
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


"""--------------------------------------------------------------------------
MESSAGE RELATED
--------------------------------------------------------------------------"""

@router.get("/physical/messages/{uid}", tags=['messages'])
async def get_physical_timeseries(
        request: Request,
        uid: int,
        count: Annotated[int | None, Query(gt=0, le=65536)] = None,
        last: str = None,
        start: datetime.datetime = None,
        end: datetime.datetime = None,
        only_timestamp: bool = False):
    """
    Get the physical_timeseries entries described by the physical device uid and the parameters.

    Args:
        request: The HTTP request object.
        uid: The unique identifier of the physical device.
        count: The maximum number of entries to return.
        last: Return messages from the last nx interval where n is a number and x is 'h'ours, 'd'ays, 'w'eeks, 'm'onths, 'y'ears.
        start: The start date and time of the time range.
        end: The end date and time of the time range.
        only_timestamp: Whether to only return the timestamp of the entries.

    Returns:
        A list of dictionaries containing the entries.

    Raises:
        HTTPException: If an error occurs.
    """
    try:
        #logging.info(f'start: {start.isoformat() if start is not None else start}, end: {end.isoformat() if end is not None else end}, count: {count}, only_timestamp: {only_timestamp}')
        if end is not None:
            if start is not None and start >= end:
                raise HTTPException(status_code=422, detail={"detail": [{"loc": ["query", "start"], "msg": "ensure start value is less than end"}]})
            if count is not None and start is None:
                raise HTTPException(status_code=422, detail={"detail": [{"loc": ["query", "count"], "msg": "only count and end is not supported"}]})

        if last is not None:
            # last over-rides start/end
            end = datetime.datetime.now(datetime.timezone.utc)

            try:
                i = int(last[:-1])
            except:
                raise HTTPException(status_code=422, detail={"detail": [{"loc": ["query", "last"], "msg": "the first part of last must be an integer"}]})

            unit = last[-1]

            if unit == 'h':
                diff = datetime.timedelta(hours=i)
            elif unit == 'd':
                diff = datetime.timedelta(days=i)
            elif unit == 'w':
                diff = datetime.timedelta(weeks=i)
            elif unit == 'm':
                diff = datetime.timedelta(weeks=i*4)
            elif unit == 'y':
                diff = datetime.timedelta(weeks=i*52)
            else:
                raise HTTPException(status_code=422, detail={"detail": [{"loc": ["query", "last"], "msg": "only h/d/w/m/y supported"}]})

            start = end - diff

        msgs = dao.get_physical_timeseries_message(uid, start, end, count, only_timestamp)
        if msgs is None:
            raise HTTPException(status_code=404, detail="Failed to retrieve messages")

        #logging.info(msgs)
        #logging.info(f'read {len(msgs)} messages')
        return msgs
    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)

"""--------------------------------------------------------------------------
USER AUTHENTICATION
--------------------------------------------------------------------------"""

# Get user token
@router.get("/token", tags=['User Authentication'], dependencies=[Depends(http_basic_auth)])
async def get_user_token(request: Request) -> str:
    """
    Get user token from database if user is authenticated
    """
    basic_auth = request.headers['Authorization'].split(' ')[1]
    username, password = base64.b64decode(basic_auth).decode().split(":")
    user_auth_token = dao.user_get_token(username=username, password=password)
    if user_auth_token != None:
        return user_auth_token
    else:
        raise HTTPException(status_code=403, detail="Incorrect username or password")


# Change users password
@router.post("/change-password", tags=['User Authentication'], dependencies=[Depends(token_auth_scheme)])
async def change_password(password:str, request:Request) -> str:
    """
    Change users password
    """
    try:
        user_auth_token=dao.user_change_password_and_token(new_passwd=password, prev_token=request.headers['Authorization'].replace("Bearer ",""))
        return user_auth_token

    except dao.DAOException as err:
        raise HTTPException(status_code=500, detail=err.msg)


app = FastAPI(title='IoT Device Broker', version='1.0.0')
app.include_router(router)


@app.middleware("http")
async def check_auth_header(request: Request, call_next):
    
    try:
        if not request.url.path in ['/docs', '/openapi.json', '/broker/api/token']:
            if not 'Authorization' in request.headers:
                return Response(content="", status_code=401)

            token = request.headers['Authorization'].split(' ')[1]
            is_valid=dao.token_is_valid(token)

            if not is_valid:
                print(f'Authentication failed for url: {request.url}')
                return Response(content="", status_code=401)

            if request.method != 'GET':
                user=dao.get_user(auth_token=token)
                if user is None or user.read_only is True:
                    return Response(content="", status_code=403)
    except:
        return Response(content="", status_code=401)

    return await call_next(request)
