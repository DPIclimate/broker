"""
The logical mapper claims pending rows from the physical_timeseries table
and determines which logical device they should be sent to.

When a mapping is active, the existing physical_timeseries row is updated
with the logical uid.
"""

import datetime
import logging
import signal
import sys
import time
from typing import Any, Dict

import dateutil.parser

import BrokerConstants
import api.client.DAO as dao
import util.LoggingUtil as lu

_finish = False

_sleep_time = 5
_batch_size = 100

_max_delta = datetime.timedelta(hours=-1)

logger = logging.getLogger(__name__)


def _fatal_db_exception(msg: str) -> int:
    global _finish

    logger.exception(msg)
    _finish = True
    try:
        dao.stop()
    except BaseException:
        logger.exception('Failed to stop DAO after database exception.')
    return 1


def sigterm_handler(sig_no, stack_frame) -> None:
    """
    Handle SIGTERM from docker by closing DB resources and setting a
    flag to tell the main loop to exit.
    """
    global _finish

    logger.info(f'{signal.strsignal(sig_no)}, setting _finish to True')
    _finish = True
    dao.stop()


def _drop_row(pts_uid: int, msg: Dict[str, Any], reason: str) -> None:
    lu.cid_logger.error(reason, extra=msg)
    dao.mark_physical_timeseries_message_failed(pts_uid)


def process_row(pts_uid: int, msg: Dict[str, Any]) -> None:
    p_uid = msg.get(BrokerConstants.PHYSICAL_DEVICE_UID_KEY)
    if not isinstance(p_uid, int):
        _drop_row(pts_uid, msg, 'Physical uid not found in message, dropping row.')
        return

    pd = dao.get_physical_device(p_uid)
    if pd is None:
        _drop_row(pts_uid, msg, 'Physical device not found, dropping row.')
        return

    lu.cid_logger.info(f'Accepted message from {p_uid}, {pd.name}', extra=msg)

    mapping = dao.get_current_device_mapping(p_uid)
    if mapping is None or mapping.is_active is not True:
        if mapping is None:
            lu.cid_logger.info(f'No device mapping found for {pd.source_ids}, cannot continue. Dropping message.', extra=msg)
        else:
            lu.cid_logger.info(f'Mapping for {pd.source_ids} is paused, cannot continue. Dropping message.', extra=msg)
        # This row was intentionally dropped and should not be retried.
        dao.mark_physical_timeseries_message_processed(pts_uid)
        return

    l_uid = mapping.ld.uid
    msg[BrokerConstants.LOGICAL_DEVICE_UID_KEY] = l_uid

    # Determine if the message has a future timestamp.
    ts_str = msg.get(BrokerConstants.TIMESTAMP_KEY)
    try:
        ts = dateutil.parser.isoparse(ts_str)
    except Exception:
        _drop_row(pts_uid, msg, 'Message with invalid timestamp. Dropping message.')
        return

    utc_now = datetime.datetime.now(datetime.timezone.utc)
    ts_delta = utc_now - ts

    # Drop messages with a timestamp more than 1 hour in the future.
    if ts_delta < _max_delta:
        _drop_row(pts_uid, msg, 'Message with future timestamp. Dropping message.')
        return

    # Update the existing row now that the mapping decision is known.
    dao.map_physical_timeseries_message(pts_uid, l_uid, msg)

    ld = mapping.ld
    if ts > utc_now:
        # If the timestamp is a bit in the future then make the last seen time 'now'.
        ld.last_seen = utc_now
    else:
        ld.last_seen = ts

    msg_ptr = {
        BrokerConstants.CORRELATION_ID_KEY: msg[BrokerConstants.CORRELATION_ID_KEY],
        BrokerConstants.TIMESTAMP_KEY: msg[BrokerConstants.TIMESTAMP_KEY],
        BrokerConstants.PHYSICAL_DEVICE_UID_KEY: p_uid,
        BrokerConstants.LOGICAL_DEVICE_UID_KEY: l_uid,
        BrokerConstants.PHYSICAL_TIMESERIES_UID_KEY: pts_uid
    }

    lu.cid_logger.info(f'Timestamp from message for LD last seen update: {ld.last_seen}', extra=msg)
    ld.properties[BrokerConstants.LAST_MSG] = msg_ptr
    dao.update_logical_device(ld)

    dao.mark_physical_timeseries_message_processed(pts_uid)


def main():
    """
    Poll physical_timeseries for claimed batches.
    """
    global _finish

    logger.info('===============================================================')
    logger.info('               STARTING LOGICAL MAPPER')
    logger.info('===============================================================')

    # TODO: Remove this startup reset before enabling multi-mapper mode.
    # Any rows left in a claimed state after a crash should be retried.
    try:
        dao.reset_claimed_physical_timeseries_messages()
    except dao.DAOException:
        return _fatal_db_exception('Database exception while resetting claimed physical_timeseries rows.')

    while not _finish:
        try:
            rows = dao.claim_unmapped_physical_timeseries_batch(_batch_size)
            if len(rows) < 1:
                time.sleep(_sleep_time)
                continue

            for pts_uid, msg in rows:
                if _finish:
                    break

                try:
                    process_row(pts_uid, msg)
                except dao.DAOException:
                    return _fatal_db_exception(f'Database exception while processing physical_timeseries uid {pts_uid}.')
                except Exception:
                    logger.exception(f'Error processing physical_timeseries uid {pts_uid}. Re-queueing row.')
                    try:
                        dao.mark_physical_timeseries_message_pending(pts_uid)
                    except dao.DAOException:
                        return _fatal_db_exception(f'Database exception while marking physical_timeseries uid {pts_uid} pending.')
                    except Exception:
                        logger.exception(f'Failed to mark physical_timeseries uid {pts_uid} as pending.')
        except dao.DAOException:
            return _fatal_db_exception('Database exception while polling physical_timeseries.')
        except Exception:
            logger.exception('Error while polling physical_timeseries.')
            time.sleep(_sleep_time)

    return 0


if __name__ == '__main__':
    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)
    signal.signal(signal.SIGINT, sigterm_handler)

    # Does not return until SIGTERM is received.
    exit_code = main()
    logger.info('Exiting.')
    sys.exit(exit_code)
