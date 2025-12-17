#
# The sensor_check module performs an SCMN-specific check that all configured sensors are
# present in messages. This is to catch instances such as when the Tocal ATM-41 went offline
# and it was not noticed.
#

# The SCMN database has a model of the field installation - every location and which sensors
# are present at each position, down to the SDI-12 ID string.

import datetime as dt
import logging
import quality
import sqlalchemy as sqla

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

"""
                     Table "location.site"
       Column       |  Type   | Collation | Nullable | Default
--------------------+---------+-----------+----------+---------
 site_id            | integer |           | not null |
 site_name          | text    |           |          |
 site_contact       | text    |           |          |
 site_organisation  | text    |           |          |
 site_contact_email | text    |           |          |
 site_contact_phone | text    |           |          |


                      Table "location.location"
    Column     |       Type       | Collation | Nullable | Default
---------------+------------------+-----------+----------+---------
 location_id   | integer          |           | not null |
 location_name | text             |           |          |
 site_id       | integer          |           |          |
 latitude      | double precision |           |          |
 longitude     | double precision |           |          |
 elevation     | double precision |           |          |
 context       | text             |           |          |


                               Table "main.mapping"
        Column         |           Type           | Collation | Nullable | Default
-----------------------+--------------------------+-----------+----------+---------
 row_id                | integer                  |           | not null |
 location_id           | integer                  |           |          |
 sensor_serial_id      | text                     |           |          |
 sensor_model_id       | integer                  |           |          |
 installer_id          | integer                  |           |          |
 position              | integer                  |           |          |
 status                | text                     |           |          |
 timestamp_installed   | timestamp with time zone |           |          |
 timestamp_uninstalled | timestamp with time zone |           |          |
"""


# site_id > 1 skips the test site.
_position_has_data_qry = """
 WITH expected_pairs AS (
  -- Get all location_id and position combinations that should exist
  -- from mapping table where status is 'Installed'
  SELECT distinct
    s.site_id, s.site_name, m.location_id, l.location_name, m.position
  FROM main.mapping m
  left join location.location l on l.location_id = m.location_id
  left join location.site s on s.site_id = l.site_id
  where s.site_id > 1 and m.status = 'Installed'
),
recent_sensor_data AS (
  -- Get unique location_id and position combinations from sensors table
  -- that were added in the last day
  SELECT DISTINCT
    s.site_id, s.site_name, m.location_id, l.location_name, m.position
  FROM main.sensors m
  left join location.location l on l.location_id = m.location_id
  left join location.site s on s.site_id = l.site_id
  WHERE s.site_id > 1 and m.ts >= :report_date
),
reading_status as (
SELECT
  ep.site_id, ep.site_name, ep.location_id, ep.location_name, ep.position,
  CASE
    WHEN rsd.location_id IS NOT NULL THEN TRUE
    ELSE FALSE
  END AS seen_in_last_day
FROM expected_pairs ep
LEFT JOIN recent_sensor_data rsd
  ON ep.location_id = rsd.location_id
  AND ep.position = rsd.position
ORDER BY ep.location_id, ep.position)
select * from reading_status where seen_in_last_day = false"""


def run_check() -> str:
    """
    Report on nodes where one or more sensors are missing from the latest message.

    This is still possibly too coarse, it will only check if no readings have come in
    from a position. That equates to an entire sensor failing. But this may be good enough.
    """

    rf = quality.ReportFragment(quality.report_root, 'Missing Sensors')
    rf.text = '\n> Nodes where sensor positions are missing.\n\n'

    with quality.ts_engine.connect() as conn:
        # Builds a map of locations, with the sensor info for each location. This can be
        # checked against the most recent values to check for missing sensors or mismatched
        # sensor IDs.
        curs = conn.execute(sqla.text(_position_has_data_qry), parameters={'report_date': quality.report_date})

        current_location_id = None
        current_location_name = None
        positions_list = []
        rows = []

        for site_id, site_name, location_id, location_name, position, is_present in curs:
            quality.emit_report = True

            if location_id != current_location_id:
                tdelta = dt.timedelta()
                try:
                    # A last_seen of None means it's never been seen? Probably not this check's problem.
                    last_seen = quality.devs[current_location_id][1]
                    tdelta = quality.report_date - last_seen
                except:
                    pass

                if tdelta.days > 0:
                    logger.info(f'{current_location_id} last seen {tdelta} ago, skip missing sensors')
                else:
                    if current_location_id is not None:
                        rows.append(f"| {current_location_id} &mdash; {current_location_name} | {', '.join(map(str, positions_list))} |")

                current_location_id = location_id
                current_location_name = location_name
                positions_list = [position]
            else:
                # Same location, add position to list
                positions_list.append(position)

        # Add the last location after the loop ends
        if current_location_id is not None:
            rows.append(f"| {current_location_id} &mdash; {current_location_name} | {', '.join(map(str, positions_list))} |")

        markdown_table = "| Location | Positions |\n"
        markdown_table += "|---|---:|\n"
        markdown_table += "\n".join(rows)

    rf.always_emit = quality.emit_report
    rf.text += markdown_table
