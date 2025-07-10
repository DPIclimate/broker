--SQL Code for creating schema and table for SCMN
-- create schema: main
create schema main;
-- create table: mapping
create table main.mapping(
   row_id int constraint mapping_pk primary key,
   location_id int,
   sensor_serial_id text,
   sensor_model_id int,
   installer_id int,
   position int,
   status text,
   timestamp_installed timestamptz,
   timestamp_uninstalled timestamptz
);
-- create table: installer
create table main.installer(
   installer_id int constraint installer_pk primary key,
   installer_contact text,
   installer_organisation text,
   installer_email text,
   installer_phone text
);
-- create schema: location
create schema location;
-- create table: location
create table location.location(
   location_id int constraint location_pk primary key,
   location_name text,
   site_id int,
   latitude float,
   longitude float,
   elevation float,
   context text
);
-- create table: calibration
create table location.calibration(
   location_id int,
   calibration_id int constraint calibration_pk primary key,
   calibration_date timestamptz,
   calibration_position text,
   calibration_variable text,
   calibration_formula text,
   calibration_notes text
);
-- create table: field_sample
create table location.field_sample(
   location_id int,
   field_sample_id int constraint field_sample_pk primary key,
   sample_date timestamptz,
   phc float,
   clay_percentage float,
   sand_percentage float,
   silt_percentage float,
   n float,
   k float,
   soc float,
   bdw float
);
-- create table: site
create table location.site(
   site_id int constraint site_pk primary key,
   site_name text,
   site_contact text,
   site_organisation text,
   site_contact_email text,
   site_contact_phone text
);
-- create table: site_historical_weather
create table location.site_historical_weather(
   site_id int,
   month int,
   temperature_maximum float,
   temperature_minimum float,
   rainfall_total float
);
-- create table: pasture_sample
create table location.pasture_sample(
   site_id int,
   pasture_sample_id int,
   sample_date timestamptz,
   latitude float,
   longitude float,
   elevation float,
   dry_matter float,
   moisture float,
   inorganic_ash float,
   ndf float,
   adf float,
   crude_protein float,
   metabolisable_energy float,
   dmd float,
   organic_matter float,
   domd float,
   wsc float,
   afia_grade float
);
-- create schema: sensor
create schema sensor;
-- create table: sensor_model
create table sensor.sensor_model(
   sensor_model_id int,
   sensor_model_name text,
   application text
);
-- create table: sensor_variable
create table sensor.sensor_variable(
   sensor_model_id int,
   sensor_variable_id int constraint sensor_variable_pk primary key,
   variable_name text,
   variable_units_raw text,
   variable_units text,
   claimed_accuracy float,
   claimed_accuracy_unit text,
   minimum_logical_value float,
   maximum_logical_value float,
   claimed_reliability float,
   claimed_reliability_unit text,
   adjustment_formula text,
   drift_over_time float,
   notes text
);
-- create table: sensor_manufacturer
create table sensor.sensor_manufacturer(
   sensor_model_id int,
   manufacturer_id int constraint sensor_manufacturer_pk primary key,
   contact text,
   organisation text,
   email text,
   phone text
);
-- create table: sensor_supplier
create table sensor.sensor_supplier(
   sensor_model_id int,
   supplier_id int constraint sensor_supplier_pk primary key,
   status text,
   timestamp_start text,
   timestamp_end text,
   contact text,
   organisation text,
   email text,
   phone text
);
