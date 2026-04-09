"""
The logical mapper claims pending rows from the physical_timeseries table
and writes logical rows to logical_timeseries.

When a variable-map exists for a physical device in devs.json, one or more
logical messages may be generated from a single source message.
"""

import copy
import datetime
import json
import logging
from pathlib import Path
import signal
import sys
import time
from typing import Any, Dict, List

import dateutil.parser

import BrokerConstants
import api.client.DAO as dao
import util.LoggingUtil as lu

_finish = False

_sleep_time = 5
_batch_size = 100

_max_delta = datetime.timedelta(hours=-1)
_variable_maps: Dict[int, List[Dict[str, Any]]] = {}

logger = logging.getLogger(__name__)


def _load_variable_maps() -> Dict[int, List[Dict[str, Any]]]:
    cfg_path = Path(__file__).with_name('devs.json')
    try:
        with cfg_path.open('r', encoding='utf-8') as fp:
            obj = json.load(fp)
    except FileNotFoundError:
        logger.warning(f'Variable-map config file not found: {cfg_path}. Starting with empty maps.')
        return {}
    except json.JSONDecodeError as err:
        logger.warning(f'Variable-map config file is invalid JSON: {cfg_path}: {err}. Starting with empty maps.')
        return {}
    except Exception as err:
        logger.warning(f'Failed reading variable-map config file: {cfg_path}: {err}. Starting with empty maps.')
        return {}

    templates = obj.get('templates', {})
    if not isinstance(templates, dict):
        logger.warning(f'Variable-map config has invalid templates object: {cfg_path}. Starting with empty maps.')
        return {}

    physical_device_templates = templates.get('physical_device_templates', [])
    template_by_name: Dict[str, Dict[str, Any]] = {}
    for template in physical_device_templates:
        try:
            template_by_name[template['name']] = template['variables']
        except Exception:
            logger.warning(f'Ignoring invalid physical_device_template entry in {cfg_path}: {template}')

    maps = templates.get('physical_to_logical_variable_maps', {})
    if not isinstance(maps, dict):
        logger.warning(f'physical_to_logical_variable_maps is missing/invalid in {cfg_path}. Starting with empty maps.')
        return {}

    out: Dict[int, List[Dict[str, Any]]] = {}
    for p_uid_str, entries in maps.items():
        if not isinstance(p_uid_str, str):
            continue
        if p_uid_str.startswith('_'):
            continue
        try:
            p_uid = int(p_uid_str)
        except ValueError:
            logger.warning(f'Invalid physical_to_logical_variable_maps physical device key: {p_uid_str}')
            continue

        if isinstance(entries, list):
            resolved_entries = []
            for entry in entries:
                template_name = entry.get('physical_device_template')
                if template_name is None:
                    resolved_entries.append(entry)
                    continue

                template_variables = template_by_name.get(template_name)
                if template_variables is None:
                    logger.warning(
                        f'physical_to_logical_variable_maps for p_uid {p_uid} references unknown '
                        f'physical_device_template {template_name}.'
                    )
                    continue

                resolved_entry = dict(entry)
                resolved_entry['variables'] = template_variables
                resolved_entries.append(resolved_entry)

            out[p_uid] = resolved_entries

    logger.info(f'Loaded physical_to_logical_variable_maps for {len(out)} physical devices.')
    return out


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


def _build_pass_through_message(msg: Dict[str, Any], p_uid: int, l_uid: int) -> Dict[str, Any]:
    out_msg = copy.deepcopy(msg)
    out_msg[BrokerConstants.PHYSICAL_DEVICE_UID_KEY] = p_uid
    out_msg[BrokerConstants.LOGICAL_DEVICE_UID_KEY] = l_uid
    out_msg.setdefault(BrokerConstants.TIMESERIES_KEY, [])
    return out_msg


def _build_transformed_messages(msg: Dict[str, Any], map_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    source_ts_index: Dict[str, List[Dict[str, Any]]] = {}
    for dot in msg[BrokerConstants.TIMESERIES_KEY]:
        input_name = dot['name']
        if input_name not in source_ts_index:
            source_ts_index[input_name] = []
        source_ts_index[input_name].append(dot)

    generated: List[Dict[str, Any]] = []
    for entry in map_entries:
        l_uid = entry[BrokerConstants.LOGICAL_DEVICE_UID_KEY]
        variables = entry['variables']

        out_ts = []
        for source_name, variable_def in variables.items():
            src_dots = source_ts_index.get(source_name)
            if src_dots is None:
                continue

            for src_dot in src_dots:
                transformed = False
                dot_value = src_dot['value']
                transformation = variable_def.get('transform')

                if transformation is not None:
                    transformed = True
                    value = float(dot_value)
                    dot_value = eval(transformation)

                out_dot = {
                    'name': variable_def['logical_name'],
                    'value': dot_value,
                    'type': variable_def['type']
                }

                if transformed is True:
                    out_dot['raw_value'] = src_dot['value']

                if BrokerConstants.TIMESTAMP_KEY in src_dot:
                    out_dot[BrokerConstants.TIMESTAMP_KEY] = src_dot[BrokerConstants.TIMESTAMP_KEY]

                out_ts.append(out_dot)

        # A map entry with no matching source variables is skipped.
        if len(out_ts) < 1:
            continue

        out_msg = copy.deepcopy(msg)
        out_msg[BrokerConstants.LOGICAL_DEVICE_UID_KEY] = l_uid
        out_msg[BrokerConstants.TIMESERIES_KEY] = out_ts
        generated.append(out_msg)

    return generated


def _update_logical_device_metadata(logical_msg: Dict[str, Any], pts_uid: int) -> None:
    l_uid = int(logical_msg[BrokerConstants.LOGICAL_DEVICE_UID_KEY])
    ld = dao.get_logical_device(l_uid)
    if ld is None:
        lu.cid_logger.warning(f'Logical device {l_uid} not found while updating metadata.', extra=logical_msg)
        return

    ts = dateutil.parser.isoparse(logical_msg[BrokerConstants.TIMESTAMP_KEY])
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    if ts > utc_now:
        ld.last_seen = utc_now
    else:
        ld.last_seen = ts

    if ld.properties is None:
        ld.properties = {}

    ld.properties[BrokerConstants.LAST_MSG] = {
        BrokerConstants.CORRELATION_ID_KEY: logical_msg[BrokerConstants.CORRELATION_ID_KEY],
        BrokerConstants.TIMESTAMP_KEY: logical_msg[BrokerConstants.TIMESTAMP_KEY],
        BrokerConstants.PHYSICAL_DEVICE_UID_KEY: logical_msg[BrokerConstants.PHYSICAL_DEVICE_UID_KEY],
        BrokerConstants.LOGICAL_DEVICE_UID_KEY: logical_msg[BrokerConstants.LOGICAL_DEVICE_UID_KEY],
        BrokerConstants.PHYSICAL_TIMESERIES_UID_KEY: pts_uid
    }
    dao.update_logical_device(ld)


def process_row(pts_uid: int, msg: Dict[str, Any]) -> None:
    global _variable_maps

    try:
        p_uid = int(msg[BrokerConstants.PHYSICAL_DEVICE_UID_KEY])
        ts_str = msg[BrokerConstants.TIMESTAMP_KEY]
        ts = dateutil.parser.isoparse(ts_str)
    except Exception:
        _drop_row(pts_uid, msg, 'Message missing required fields or has invalid timestamp. Dropping message.')
        return

    utc_now = datetime.datetime.now(datetime.timezone.utc)
    ts_delta = utc_now - ts

    # Drop messages with a timestamp more than 1 hour in the future.
    if ts_delta < _max_delta:
        _drop_row(pts_uid, msg, 'Message with future timestamp. Dropping message.')
        return

    pd = dao.get_physical_device(p_uid)
    if pd is None:
        _drop_row(pts_uid, msg, 'Physical device not found, dropping row.')
        return

    lu.cid_logger.info(f'Accepted message from {p_uid}, {pd.name}', extra=msg)

    # DAO resolves the current mapping from the open-ended [start, end) mapping range.
    mapping = dao.get_current_device_mapping(p_uid)
    map_entries = _variable_maps.get(p_uid, [])

    logical_msgs = []
    if len(map_entries) > 0:
        try:
            logical_msgs = _build_transformed_messages(msg, map_entries)
        except Exception:
            _drop_row(pts_uid, msg, 'Message does not match variable-map structure. Dropping message.')
            lu.cid_logger.info('Message processing error.', extra=msg)
            sys.exit(1)

        # If no transformed rows were produced, create a fallback row only when
        # there is an active physical->logical mapping.
        if len(logical_msgs) < 1 and mapping is not None and mapping.is_active is True:
            logical_msgs.append(_build_pass_through_message(msg, p_uid, mapping.ld.uid))
    else:
        if mapping is None or mapping.is_active is not True:
            if mapping is None:
                lu.cid_logger.info(f'No device mapping found for {pd.source_ids}, cannot continue. Dropping message.', extra=msg)
            else:
                lu.cid_logger.info(f'Mapping for {pd.source_ids} is paused, cannot continue. Dropping message.', extra=msg)
            # This row was intentionally dropped and should not be retried.
            dao.mark_physical_timeseries_message_skipped(pts_uid)
            return

        l_uid = mapping.ld.uid
        msg[BrokerConstants.LOGICAL_DEVICE_UID_KEY] = l_uid

        # Preserve existing behaviour for non-variable-map devices by updating
        # the source physical_timeseries row with the resolved logical uid.
        dao.map_physical_timeseries_message(pts_uid, l_uid, msg)
        logical_msgs.append(_build_pass_through_message(msg, p_uid, l_uid))

    for logical_msg in logical_msgs:
        dao.insert_logical_timeseries_message(logical_msg)
        _update_logical_device_metadata(logical_msg, pts_uid)

    dao.mark_physical_timeseries_message_success(pts_uid)


def main():
    """
    Poll physical_timeseries for claimed batches.
    """
    global _finish

    global _variable_maps

    logger.info('===============================================================')
    logger.info('               STARTING LOGICAL MAPPER')
    logger.info('===============================================================')

    _variable_maps = _load_variable_maps()

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
