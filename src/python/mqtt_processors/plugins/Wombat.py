import dateutil.parser, json, uuid
import BrokerConstants
from pdmodels.Models import PhysicalDevice
import util.LoggingUtil as lu
import api.client.DAO as dao

TOPICS = ['wombat']

def on_message(message, properties):
    correlation_id = str(uuid.uuid4())
    lu.cid_logger.info(f'Message as received: {message}', extra={BrokerConstants.CORRELATION_ID_KEY: correlation_id})

    msg = {}
    try:
        msg = json.loads(message)
    except Exception as e:
        raise Exception(f'JSON parsing failed')

    # This code could put the cid into msg (and does so later) and pass msg into the lu_cid
    # logger calls. However, for consistency with other modules and to avoid problems if this code
    # is ever copy/pasted somewhere we will stick with building a msg_with_cid object and using
    # that for logging.
    msg_with_cid = {BrokerConstants.CORRELATION_ID_KEY: correlation_id, BrokerConstants.RAW_MESSAGE_KEY: msg}

    # Record the message to the all messages table before doing anything else to ensure it
    # is saved. Attempts to add duplicate messages are ignored in the DAO.
    msg_ts = dateutil.parser.isoparse(msg[BrokerConstants.TIMESTAMP_KEY])
    dao.add_raw_json_message(BrokerConstants.WOMBAT, msg_ts, correlation_id, msg)

    source_ids = msg['source_ids']
    serial_no = source_ids['serial_no']
    lu.cid_logger.info(f'Accepted message from {serial_no}', extra=msg_with_cid)

    # Find the device using only the serial_no.
    find_source_id = {'serial_no': serial_no}
    pds = dao.get_pyhsical_devices_using_source_ids(BrokerConstants.WOMBAT, find_source_id)
    if len(pds) < 1:
        lu.cid_logger.info('Device not found, creating physical device.', extra=msg_with_cid)

        props = {
            BrokerConstants.CREATION_CORRELATION_ID_KEY: correlation_id,
            BrokerConstants.LAST_MSG: msg
        }

        device_name = f'Wombat-{serial_no}'
        pd = PhysicalDevice(source_name=BrokerConstants.WOMBAT, name=device_name, location=None, last_seen=msg_ts, source_ids=source_ids, properties=props)
        pd = dao.create_physical_device(pd)
    else:
        # Update the source_ids because the Wombat firmware was updated to include the SDI-12 sensor
        # IDs in the source_ids object after physical devices with only the serial_no had been created.
        # Additionally, something like an AWS might get replaced so there will be a new SDI-12 ID for that.
        pd.source_ids = source_ids
        pd = pds[0]
        pd.last_seen = msg_ts
        pd.properties[BrokerConstants.LAST_MSG] = msg
        pd = dao.update_physical_device(pd)

    if pd is None:
        lu.cid_logger.error(f'Physical device not found, message processing ends now. {correlation_id}', extra=msg_with_cid)
        raise Exception(f'Physical device not found')

    lu.cid_logger.info(f'Using device id {pd.uid}', extra=msg_with_cid)

    msg[BrokerConstants.CORRELATION_ID_KEY] = correlation_id
    msg[BrokerConstants.PHYSICAL_DEVICE_UID_KEY] = pd.uid

    lu.cid_logger.debug(f'Publishing message: {msg}', extra=msg_with_cid)
    return {
        'messages': [msg],
        'errors': []
    }
