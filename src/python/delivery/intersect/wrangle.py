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


import pandas as pd
import os, re
import datetime
import dateutil.parser as dup
import logging

from pathlib import Path
from psycopg2.extras import RealDictCursor

"""
SELECT location_id, calibration_position::integer as position, calibration_variable as variable, calibration_formula as adjustment_formula
  FROM location.calibration WHERE location_id = 26 ORDER BY calibration_date
"""

_clear_cache_flag_file = Path(os.environ['CLEAR_CALIBRATION_CACHE_FILE'])

_var_info_cache = {}


# Queries now use positional parameters so they can be prepared and avoid SQL injection attacks.
_cal_query = """SELECT location_id, calibration_position::integer as position, calibration_variable as variable, calibration_formula as adjustment_formula FROM location.calibration WHERE location_id = %s ORDER BY calibration_date"""
_log_query = """SELECT location_id, position, variable_name as variable, adjustment_formula, minimum_logical_value, maximum_logical_value FROM main.mapping LEFT JOIN sensor.sensor_variable ON sensor_variable.sensor_model_id = mapping.sensor_model_id WHERE mapping.location_id = %s"""
_empty_frame = pd.DataFrame(columns=['location_id', 'position', 'variable', 'adjustment_formula'])

def get_variable_info(location_id, con_wrangle):
    """
    This function is for extracting information for the data quality assurance testing in wrangle.wrangle
    """

    if _clear_cache_flag_file.exists() and _clear_cache_flag_file.is_file():
        logging.info('Clearing calibration values cache.')
        _var_info_cache.clear()
        _clear_cache_flag_file.unlink()

    if location_id in _var_info_cache:
        return _var_info_cache[location_id]

    try:
        df_cal = _empty_frame

        with con_wrangle.cursor(cursor_factory=RealDictCursor) as curs:
            logging.info(curs.mogrify(_cal_query, (location_id,)))
            curs.execute(_cal_query, (location_id,))
            cal_rows = curs.fetchall()

            logging.info(curs.mogrify(_log_query, (location_id,)))
            curs.execute(_log_query, (location_id,))
            log_rows = curs.fetchall()

        if len(cal_rows) > 0:
            df_cal = pd.DataFrame(cal_rows)

        df_log = pd.DataFrame(log_rows)
        merged_df = df_log[['location_id', 'position', 'variable', 'adjustment_formula', 'minimum_logical_value', 'maximum_logical_value']].merge(
            df_cal[['location_id', 'position', 'variable', 'adjustment_formula']],
            on=['location_id', 'position', 'variable'],
            how='left')

        # Replace NaN values in 'adjustment_formula' with values from df_log
        merged_df['adjustment_formula'] = merged_df['adjustment_formula_y'].combine_first(merged_df['adjustment_formula_x'])
        merged_df.drop(['adjustment_formula_x', 'adjustment_formula_y'], axis=1, inplace=True)

        if location_id not in _var_info_cache:
            _var_info_cache[location_id] = merged_df

        return merged_df
    except Exception as e:
        logging.exception("Error in get_variable_info")
        return None


_skip_names = ('rsrp', 'rsrq')
_timestamp_check_delta = datetime.timedelta(days=180)
_empty_list = []

def wrangle(msg_dict, conn):
    """
    This function is used to wrangle the raw data and slightly odd json format from the DPI SCMN broker
    into a format ready for the processed database.

    :param msg_dict:
    :param conn:
    :return:
    """
    try:
        serial_ids = pd.DataFrame(msg_dict['source_ids']['sdi-12'], columns=['String'])
        serial_ids = serial_ids['String'].str.split(r'\s+', expand=True)
        serial_ids.columns = ['position', 'model_abrev', 'serial_id']
        serial_ids['position'] = serial_ids['position'].str.extract(r'(\d+)')
        serial_ids['position'] = serial_ids['position'].str[0]
        serial_ids['serial_id'] = serial_ids['serial_id'].str.replace("']", '')

        timestamp = dup.isoparse(msg_dict['timestamp'])

        broker_correlation_id = msg_dict['broker_correlation_id']

        location_id = msg_dict['l_uid']

        # Check if timestamp is within 6 months of current date
        if abs(datetime.datetime.now(datetime.timezone.utc) - timestamp) <= _timestamp_check_delta:
            timestamp_valid = True
        else:
            timestamp_valid = False

        output = []

        # Get quality assurance dataframe.
        df_lookup = get_variable_info(location_id, conn)
        if df_lookup.shape[0] > 0:
            for timeseries_obj in msg_dict['timeseries']:
                try:
                    variable = timeseries_obj['name']
                    value = float(timeseries_obj['value'])
                    if variable in _skip_names:
                        continue
                except ValueError:
                    logging.error(f'Processing exception: Invalid data - l_uid {location_id}: [{timeseries_obj}]')
                    continue

                if variable[0].isdigit():
                    position = int(variable[0])
                    variable = re.sub(r'^[^_]*_', '', variable)
                    sensor_serial_id = serial_ids.loc[serial_ids['position'] == str(position), 'serial_id'].item()
                else:
                    position = 0
                    sensor_serial_id = msg_dict['source_ids']['serial_no']

                ### Data Quality Assurance ###
                df_cal = df_lookup[(df_lookup['location_id'] == location_id) &
                                   (df_lookup['position'] == position) &
                                   (df_lookup['variable'] == variable)]
                if df_cal.shape[0] > 0:
                    df_cal = df_cal.reset_index()
                    value = eval(df_cal['adjustment_formula'][0])

                    # value error checking
                    min_value = float(df_cal['minimum_logical_value'][0])
                    max_value = float(df_cal['maximum_logical_value'][0])
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
                    logging.error(f"Processing exception: inside wrangle.wrangle: - Variable ({variable}) not available in lookup tables for logical id ({location_id}) - JSON Data: {data} ")

            return output
        else:
            logging.error(f"Processing exception: inside wrangle.wrangle: - No lookup table for logical id ({location_id}) - JSON Data: {msg_dict}")
            return _empty_list
    except Exception as ex:
        logging.exception(f"Error in wrangle.wrangle")
        return _empty_list
# end
