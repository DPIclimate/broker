#  dpi-data-pipeline - scmn_data_workflow.py
#  Description:      A function to wrangle the json data from the DPI SCMN Broker into
#                    an appropriate format.
#  Author:           Glen Charlton
#  Created:          21 Feb. 2023
#  Source:           https://github.com/IntersectAustralia/databolt-agent
#  License:          Copyright (c) 2020 Intersect Australia - All Rights Reserved
#                    Unauthorized copying of this file, via any medium is
#                    strictly prohibited. Proprietary and confidential
#
# Modified by DPIRD to integrate into the IoTa data pipeline and improve performance.

import os, re
import datetime
import dateutil.parser as dup
import logging
import util.LoggingUtil as lu

from pathlib import Path
from psycopg2.extras import RealDictCursor

_clear_cache_flag_file = Path(os.environ['CLEAR_CALIBRATION_CACHE_FILE'])

_var_info_cache = {}


# Queries now use positional parameters so they can be prepared and avoid SQL injection attacks.
_cal_query = """SELECT calibration_position::integer as position, calibration_variable as variable, calibration_formula as adjustment_formula FROM location.calibration WHERE location_id = %s ORDER BY calibration_date"""
_device_query = """SELECT position, variable_name as variable, adjustment_formula, minimum_logical_value, maximum_logical_value FROM main.mapping LEFT JOIN sensor.sensor_variable ON sensor_variable.sensor_model_id = mapping.sensor_model_id WHERE mapping.location_id = %s"""

_FORMULA = 0
_MIN_VALUE = 1
_MAX_VALUE = 2

def get_variable_info(location_id, con_wrangle, msg):
    """
    This function is for extracting information for the data quality assurance testing in wrangle.wrangle.

    Returns a dict containing the transformation formula and min/max bounds for the value of each sensor for a given device:
    {
        position: {
            variable: [adjustment_formula, minimum_logical_value, maximum_logical_value],
            ...
        },
        ...
    }
    """

    if _clear_cache_flag_file.exists() and _clear_cache_flag_file.is_file():
        lu.cid_logger.info('Clearing calibration values cache.', extra=msg)
        _var_info_cache.clear()
        _clear_cache_flag_file.unlink()

    if location_id in _var_info_cache:
        return _var_info_cache[location_id]

    try:
        with con_wrangle.cursor(cursor_factory=RealDictCursor) as curs:
            curs.execute(_cal_query, (location_id,))
            cal_rows = curs.fetchall()

            curs.execute(_device_query, (location_id,))
            device_rows = curs.fetchall()

        cal_info = {}
        for row in device_rows:
            posn = row['position']
            variable = row['variable']
            formula = row['adjustment_formula']
            min_value = row['minimum_logical_value']
            max_value = row['maximum_logical_value']
            if posn not in cal_info:
                cal_info[posn] = {}

            cal_info[posn][variable] = [formula, min_value, max_value]

        for row in cal_rows:
            posn = row['position']
            variable = row['variable']
            formula = row['adjustment_formula']
            cal_info[posn][variable][_FORMULA] = formula

        if location_id not in _var_info_cache:
            _var_info_cache[location_id] = cal_info

        return cal_info

    except Exception as e:
        lu.cid_logger.exception(f"Error in get_variable_info: {e}", extra=msg)
        return None


_skip_names = ('rsrp', 'rsrq')
_timestamp_check_delta = datetime.timedelta(days=180)


def wrangle(msg_dict, conn):
    """
    This function is used to wrangle the raw data and slightly odd json format from the DPI SCMN broker
    into a format ready for the processed database.

    :param msg_dict:
    :param conn:
    :return:
    """
    output = []

    try:
        # 113METER   TER11 302T11-00025159
        sdi12_ids = [''] * 9
        for sdi12_id in msg_dict['source_ids']['sdi-12']:
            sdi12_ids[int(sdi12_id[0])] = sdi12_id[17:]

        timestamp = dup.isoparse(msg_dict['timestamp'])

        broker_correlation_id = msg_dict['broker_correlation_id']

        location_id = msg_dict['l_uid']

        # Check if timestamp is within 6 months of current date
        if abs(datetime.datetime.now(datetime.timezone.utc) - timestamp) <= _timestamp_check_delta:
            timestamp_valid = True
        else:
            timestamp_valid = False

        # Get quality assurance dataframe.
        df_lookup = get_variable_info(location_id, conn, msg_dict)
        if df_lookup is not None:
            # This is used as the sensor ID for non-SDI12 readings.
            node_serial_no = msg_dict['source_ids']['serial_no']

            for timeseries_obj in msg_dict['timeseries']:
                try:
                    variable = timeseries_obj['name']
                    if variable in _skip_names:
                        continue

                    value = float(timeseries_obj['value'])
                except ValueError:
                    lu.cid_logger.error(f'Processing exception: Invalid data - l_uid {location_id}: [{timeseries_obj}]', extra=msg_dict)
                    continue

                if variable[0].isdigit():
                    position = int(variable[0])
                    variable = re.sub(r'^[^_]*_', '', variable)
                    sensor_serial_id = sdi12_ids[position]
                else:
                    position = 0
                    sensor_serial_id = node_serial_no

                ### Data Quality Assurance ###
                df_cal = df_lookup[position][variable]
                if df_cal is not None:
                    formula: str = df_cal[_FORMULA]
                    value = eval(formula)

                    # value error checking
                    min_value = df_cal[_MIN_VALUE]
                    max_value = df_cal[_MAX_VALUE]
                    if min_value <= value and max_value >= value and timestamp_valid:
                        err_data = False
                    else:
                        err_data = True

                    ### Edit bad names ###
                    variable = re.sub(' ', '_', variable)
                    variable = re.sub(r'\s*\((v)\)\s*', 'voltage', variable)

                    ### Correct Variable names
                    if variable == 'pulse_count':  # pulse count to precipitation after adjustment
                        variable = 'Precipitation'

                    output.append((timestamp, broker_correlation_id, location_id, sensor_serial_id, position, variable, value, err_data))
                else:
                    lu.cid_logger.error(f"Processing exception: inside wrangle.wrangle: - Variable ({variable}) not available at position {position} in lookup tables for logical id ({location_id}) - JSON Data: {msg_dict}", extra=msg_dict)

            return output
        else:
            lu.cid_logger.error(f"Processing exception: inside wrangle.wrangle: - No lookup table for logical id ({location_id}) - JSON Data: {msg_dict}", extra=msg_dict)
            return output
    except Exception as ex:
        lu.cid_logger.exception(f"Error in wrangle.wrangle", extra=msg_dict)
        return output
# end
