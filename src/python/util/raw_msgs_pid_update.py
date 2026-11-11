import logging
from typing import Tuple, Dict, List
import dotenv
import psycopg2 as pg
from psycopg2.extras import execute_values

import BrokerConstants
import LoggingUtil
import api.client.DAO as dao
from pdmodels.Models import PhysicalDevice

logger = logging.getLogger(__name__)
dotenv.load_dotenv()


def ttn_src_ids_from_msg(msg: dict) -> Tuple[str, str]:
    try:
        return msg['end_device_ids']['application_ids']['application_id'].lower(), msg['end_device_ids']['dev_eui'].lower()
    except (KeyError, TypeError, AttributeError) as e:
        raise ValueError('Invalid TTN message device identifier object') from e


def dragino_src_ids_from_msg(msg: dict) -> str:
    try:
        return msg['IMEI'].lower()
    except (KeyError, TypeError, AttributeError) as e:
        raise ValueError('Invalid Dragino message device identifier object') from e


_row_limit = 1000


def get_rows_for_dev_type(curs, dev_type, start_uid, end_uid):
    curs.execute(
        """
        SELECT uid, json_msg FROM raw_messages
        WHERE source_name = %s AND uid > %s AND uid <= %s
          AND physical_uid IS NULL
        ORDER BY uid ASC LIMIT %s
        """,
        (dev_type, start_uid, end_uid, _row_limit),
    )


def update_rows(curs, pd_updates) -> int:
    if pd_updates:
        execute_values(
            curs,
            """
            UPDATE raw_messages AS raw
            SET physical_uid = updates.physical_uid
            FROM (VALUES %s) AS updates (uid, physical_uid)
            WHERE raw.uid = updates.uid
              AND raw.physical_uid IS NULL
            """,
            pd_updates,
            page_size=_row_limit,
        )
        return curs.rowcount

    return 0


def process_ttn_msgs(start_uid: int, end_uid: int):
    ttn_dict: Dict[str, Dict[str, PhysicalDevice]] = {}

    physical_devices = dao.get_physical_devices_from_source(BrokerConstants.TTN)
    for pd in physical_devices:
        src_ids = pd.source_ids
        ttn_dict.setdefault(src_ids['app_id'].lower(), {})[src_ids['dev_eui'].lower()] = pd

    last_uid = start_uid - 1
    updated_count = 0
    logger.info('Processing raw message UIDs %s through %s inclusive', start_uid, end_uid)

    with pg.connect(application_name=__name__) as conn:
        with conn.cursor() as curs:
            while True:
                get_rows_for_dev_type(curs, BrokerConstants.TTN, last_uid, end_uid)
                rows = curs.fetchall()
                if not rows:
                    break

                pd_updates: List[Tuple[int, int]] = []
                for msg_uid, msg in rows:
                    try:
                        app_id, dev_eui = ttn_src_ids_from_msg(msg)
                        pd = ttn_dict[app_id][dev_eui]
                        pd_updates.append((msg_uid, pd.uid))
                    except ValueError:
                        logger.error('Could not extract source ids from message %s', msg_uid)
                    except KeyError:
                        logger.error('No device for %s:%s in message %s', app_id, dev_eui, msg_uid)

                if pd_updates:
                    updated_count += update_rows(curs, pd_updates)

                last_uid = rows[-1][0]
                logger.info('Processed through UID %s', last_uid)

    logger.info('Updated physical_uid on %s raw messages', updated_count)


def process_dragino_msgs(start_uid: int, end_uid: int):
    dev_dict: Dict[str, PhysicalDevice] = {}

    physical_devices = dao.get_physical_devices_from_source(BrokerConstants.DRAGINO_JSON)
    for pd in physical_devices:
        src_id = pd.source_ids['IMEI'].lower()
        dev_dict[src_id] = pd

    last_uid = start_uid - 1
    updated_count = 0
    logger.info('Processing raw message UIDs %s through %s inclusive', start_uid, end_uid)

    with pg.connect(application_name=__name__) as conn:
        with conn.cursor() as curs:
            while True:
                get_rows_for_dev_type(curs, BrokerConstants.DRAGINO_JSON, last_uid, end_uid)
                rows = curs.fetchall()
                if not rows:
                    break

                pd_updates: List[Tuple[int, int]] = []
                for msg_uid, msg in rows:
                    try:
                        imei = dragino_src_ids_from_msg(msg)
                        pd = dev_dict[imei]
                        pd_updates.append((msg_uid, pd.uid))
                    except ValueError:
                        logger.error('Could not extract source ids from message %s', msg_uid)
                    except KeyError:
                        logger.error('No device for %s in message %s', imei, msg_uid)

                if pd_updates:
                    updated_count += update_rows(curs, pd_updates)

                last_uid = rows[-1][0]
                logger.info('Processed through UID %s', last_uid)

    logger.info('Updated physical_uid on %s raw messages', updated_count)


def main():
    with pg.connect(application_name=__name__) as conn:
        with conn.cursor() as curs:
            curs.execute("select min(uid), max(uid) from raw_messages where ts < now() and ts > now() - '1 day'::interval and physical_uid is null;")
            start_uid, end_uid = curs.fetchone()

    logger.info('Processing TTN messages.')
    process_ttn_msgs(start_uid, end_uid)
    logger.info('Processing Dragino messages.')
    process_dragino_msgs(start_uid, end_uid)


if __name__ == '__main__':
    main()
