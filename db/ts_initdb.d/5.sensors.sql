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


