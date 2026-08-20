-- Export the database information used to build ICT_EAGLEIO_DEVICE_MAP in
-- src/python/receiver/ict_mqtt/main.py.
--
-- Run with psql and redirect stdout to a JSON file, for example:
--
--   psql "$DATABASE_URL" \
--     --tuples-only --no-align \
--     --file doc/ict_mqtt/export_eagleio_device_map.sql \
--     > ict_eagleio_devices.json
--
-- The result is one JSON array. An array is used instead of a JSON object so
-- duplicate physical-device names remain visible. Device names are the MQTT
-- allowlist keys, so duplicates must be resolved before generating the Python
-- map.

WITH eagleio_devices AS (
    SELECT
        pd.uid AS physical_uid,
        pd.name AS physical_name,
        pd.source_ids AS physical_source_ids,
        pd.last_seen AS physical_last_seen,
        CASE
            WHEN pd.location IS NULL THEN NULL
            ELSE jsonb_build_object(
                'latitude', ST_Y(pd.location),
                'longitude', ST_X(pd.location)
            )
        END AS physical_location,
        current_mapping.start_time AS mapping_start_time,
        current_mapping.logical_uid,
        current_mapping.logical_name,
        current_mapping.logical_last_msg
    FROM physical_devices AS pd
    LEFT JOIN LATERAL (
        -- There should be at most one open mapping. Choosing the newest one
        -- makes the export deterministic if historical data violates that
        -- expectation.
        SELECT
            plm.start_time,
            ld.uid AS logical_uid,
            ld.name AS logical_name,
            ld.properties -> 'last_msg' AS logical_last_msg
        FROM physical_logical_map AS plm
        JOIN logical_devices AS ld
            ON ld.uid = plm.logical_uid
        WHERE plm.physical_uid = pd.uid
          AND plm.end_time IS NULL
        ORDER BY plm.start_time DESC, ld.uid
        LIMIT 1
    ) AS current_mapping ON true
    WHERE pd.source_name = 'ict_eagleio'
)
SELECT jsonb_pretty(
    COALESCE(
        jsonb_agg(
            jsonb_build_object(
                'physical_uid', physical_uid,
                'physical_name', physical_name,
                'physical_source_ids', physical_source_ids,
                'physical_last_seen', physical_last_seen,
                'physical_location', physical_location,
                'mapping_start_time', mapping_start_time,
                'logical_uid', logical_uid,
                'logical_name', logical_name,
                'logical_last_msg', logical_last_msg,
                'logical_reading_names', COALESCE(
                    (
                        SELECT jsonb_agg(reading ->> 'name' ORDER BY reading_ordinal)
                        FROM jsonb_array_elements(
                            COALESCE(logical_last_msg -> 'timeseries', '[]'::jsonb)
                        ) WITH ORDINALITY AS readings(reading, reading_ordinal)
                    ),
                    '[]'::jsonb
                )
            )
            ORDER BY physical_name, physical_uid
        ),
        '[]'::jsonb
    )
)
FROM eagleio_devices;
