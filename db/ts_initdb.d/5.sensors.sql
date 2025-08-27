--SQL Code for creating schema and table for SCMN (sensors table only)

-- create table: sensors
create table main.sensors
(
    ts                    timestamp with time zone not null,
    row_id                serial,
    broker_correlation_id uuid,
    location_id            integer,
    sensor_serial_id      text,
    position              integer,
    variable                text,
    value                 double precision,
    err_data                boolean
);

SELECT create_hypertable('main.sensors','ts');

create index sensors_rowid
    on main.sensors (row_id asc);

create index sensors_ix_location_id_time
    on main.sensors (location_id, ts);

create index sensors_ix_location_id_sensor_serial
    on main.sensors (location_id, sensor_serial_id);

create index sensors_ix_location_id_time_variable
    on main.sensors (location_id, ts, variable);

create index sensors_ix_location_id_time_variable_err
    on main.sensors (location_id, ts, variable, err_data);

create index sensors_ix_location_id_time_variable_position
    on main.sensors (location_id, ts, variable, position);

create index sensors_ix_location_id_time_variable_position_err
    on main.sensors (location_id, ts, variable, position, err_data);

--
-- These views are used in the Looker Studio dashboards.
--

-- Provides access to the most recent value for any ATM41 value.
-- Use a where clause on location_id and variable to get a specific
-- value such as air temp.
create or replace view public.latest_aws_data as (
with latest_ts AS (
SELECT location_id, MAX(ts) as location_max_ts
  FROM main.sensors
  WHERE position = 8
    AND err_data = false
    AND ts >= current_date
    AND ts < now()
group by location_id
)
SELECT
  sensors.*, sensors.ts at time zone 'Australia/Sydney' as local_time,
  locn.location_name
FROM main.sensors sensors
right join latest_ts on latest_ts.location_id = sensors.location_id and latest_ts.location_max_ts = sensors.ts
join "location"."location" locn on locn.location_id = sensors.location_id
WHERE sensors.position = 8
order by location_id, variable
);

-- This is a cut-down version of the sensors_rainfall_latest view which only
-- calculates the today and yesterday columns from tipper bucket data.
-- If the view is queried before 9:00am then the sum of precipitation for each location from
-- 9:00am yesterday is returned. If the query is run at or after 9:00am then values from
-- 9:00am today are summed.
create or replace view public.daily_rainfall as (
SELECT location.site_id,
    sensor_data.location_id,
    site.site_name,
    location.location_name,
    location.latitude,
    location.longitude,
    avg(sensor_data.today) AS today,
    avg(sensor_data.yesterday) AS yesterday
   FROM location.location
     RIGHT JOIN ( SELECT t1.location_id,
            t1.variable,
            t1.today,
            t1.yesterday
           FROM ( SELECT sensors.location_id,
                    sensors.variable,
                    sensors."position",
                    sum(
                        -- If query is run before 9:00am
                        --   If reading timestamp >= yesterday 9:00am [all readings at or after 9:00am yesterday to be included; it is before 9:00am so we're still within yesterdays 9:00am to 9:00am window as 'today']
                        --     add reading to today's sum
                        -- Else [ie the query is run at or after 9:00am]
                        --   If reading timestamp >= today 9:00am [filter out yesterday's 9:00am to 9:00am readings]
                        --     add reading to today's sum
                        CASE
                            WHEN (sensors.ts AT TIME ZONE 'Australia/Sydney'::text) >=
                            CASE
                                WHEN EXTRACT(hour FROM (now() AT TIME ZONE 'Australia/Sydney'::text)) < 9::numeric THEN date_trunc('day'::text, (now() AT TIME ZONE 'Australia/Sydney'::text)) - '15:00:00'::interval
                                ELSE date_trunc('day'::text, (now() AT TIME ZONE 'Australia/Sydney'::text)) + '09:00:00'::interval
                            END THEN sensors.value
                            ELSE NULL::double precision
                        END) AS today,
                    sum(
                        CASE
                            WHEN (sensors.ts AT TIME ZONE 'Australia/Sydney'::text) >=
                            CASE
                                WHEN EXTRACT(hour FROM (now() AT TIME ZONE 'Australia/Sydney'::text)) < 9::numeric THEN date_trunc('day'::text, (now() AT TIME ZONE 'Australia/Sydney'::text)) - '1 day'::interval - '15:00:00'::interval
                                ELSE date_trunc('day'::text, (now() AT TIME ZONE 'Australia/Sydney'::text)) - '15:00:00'::interval
                            END AND (sensors.ts AT TIME ZONE 'Australia/Sydney'::text) <
                            CASE
                                WHEN EXTRACT(hour FROM (now() AT TIME ZONE 'Australia/Sydney'::text)) < 9::numeric THEN date_trunc('day'::text, (now() AT TIME ZONE 'Australia/Sydney'::text)) - '15:00:00'::interval
                                ELSE date_trunc('day'::text, (now() AT TIME ZONE 'Australia/Sydney'::text)) + '09:00:00'::interval
                            END THEN sensors.value
                            ELSE NULL::double precision
                        END) AS yesterday
                   FROM main.sensors
                  WHERE sensors.ts > now() - interval '3 days' and sensors.position = 0 and sensors.variable = 'Precipitation'::text AND sensors.err_data = false
                  GROUP BY sensors.location_id, sensors.variable, sensors."position") t1) sensor_data ON location.location_id = sensor_data.location_id
     LEFT JOIN location.site ON site.site_id = location.site_id
  GROUP BY location.site_id, sensor_data.location_id, site.site_name, location.location_name, location.latitude, location.longitude
)
