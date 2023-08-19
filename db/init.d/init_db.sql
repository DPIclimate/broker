create table if not exists sources (
    source_name text primary key not null
);

create table if not exists physical_devices (
    uid integer generated always as identity primary key,
    source_name text not null references sources,
    name text not null,
    location point,
    last_seen timestamptz,
    -- Store only top level key value pairs here; it is used
    -- for quickly finding a device using information carried
    -- in a message such as a deveui or sensor group id.
    source_ids jsonb,
    -- Store more complete information about the source device
    -- in this column. Information such as description or
    -- attributes that may be useful to downstream processes
    -- can go here.
    -- The correlation ID of the message that caused a device
    -- to be created should also be stored in here under the
    -- key creation-correlation-id.
    properties jsonb not null default '{}'
);

create table if not exists physical_timeseries ( 
    uid integer generated always as identity primary key,
    physical_uid integer not null references physical_devices(uid),
    ts timestamptz not null,
    -- The message is stored in the brokers format as a JSONB object.
    json_msg jsonb not null
);

create table if not exists raw_messages (
    uid integer generated always as identity primary key,
    source_name text not null references sources,
    -- Some front-end-processors will have the physical uid
    -- available when they write these messages so include this
    -- as an optional column. The split processing in TTN could
    -- have this updated by the second process, using the correlation id
    -- to find the raw_messages row after it has the physical device.
    physical_uid integer,
    -- The correlation ID must be generated by the front end
    -- processors that receive the messages.
    correlation_id uuid unique not null,
    ts timestamptz not null,
    -- If the source system uses JSON for its message format
    -- then the messages get stored in this column.
    json_msg jsonb,
    -- If the source system uses CSV or similar then the messages
    -- get stored in this column.
    text_msg text
);

create table if not exists device_notes (
    uid integer generated always as identity primary key,
    physical_uid integer references physical_devices(uid),
    ts timestamptz not null default now(),
    note text not null
);

create table if not exists device_blobs (
    uid integer generated always as identity primary key,
    physical_uid integer references physical_devices(uid),
    ts timestamptz not null default now(),
    data bytea not null
);

create table if not exists logical_devices (
    uid integer generated always as identity primary key,
    name text not null,
    location point,
    last_seen timestamptz,
    properties jsonb not null default '{}'
);

create table if not exists physical_logical_map (
    -- Having all columns in the primary key means there cannot be two
    -- mapping rows for the same devices at the same time.
    physical_uid integer not null references physical_devices(uid),
    logical_uid integer not null references logical_devices(uid),
    start_time timestamptz not null default now(),
    end_time timestamptz,
    constraint end_gt_start check (end_time > start_time),
    unique (logical_uid, start_time),
    primary key(physical_uid, logical_uid, start_time)
);

create table if not exists users(
    uid integer generated always as identity primary key,
    username text not null unique,
    salt text not null,
    password text not null,
    auth_token text not null,
    valid boolean not null,
    read_only boolean default True not null
);

create table if not exists data_name_map(
    input_name text not null primary key,
    std_name text not null
);

create index if not exists pd_src_id_idx on physical_devices using GIN (source_ids);

insert into sources values ('ttn'), ('greenbrain'), ('wombat'), ('ydoc'), ('ict_eagleio');

insert into data_name_map (input_name, std_name) values
    ('1_Temperature', '1_TEMPERATURE'),
    ('1_VWC', '1_VWC'),
    ('2_Temperature', '2_TEMPERATURE'),
    ('2_VWC', '2_VWC'),
    ('3_Temperature', '3_TEMPERATURE'),
    ('3_VWC', '3_VWC'),
    ('4_Temperature', '4_TEMPERATURE'),
    ('4_VWC', '4_VWC'),
    ('5_Temperature', '5_TEMPERATURE'),
    ('5_VWC', '5_VWC'),
    ('6_Temperature', '6_TEMPERATURE'),
    ('6_VWC', '6_VWC'),
    ('8_AirPressure', '8_AIRPRESSURE'),
    ('8_AirTemperature', '8_AIR_TEMPERATURE'),
    ('8_HumiditySensorTemperature', '8_HUMIDITY_SENSOR_TEMPERATURE'),
    ('8_Precipitation', '8_PRECIPITATION'),
    ('8_RH', '8_RH'),
    ('8_Solar', '8_SOLAR'),
    ('8_Strikes', '8_STRIKES'),
    ('8_VaporPressure', '8_VAPOR_PRESSURE'),
    ('8_WindDirection', '8_WIND_DIRECTION'),
    ('8_WindGustSpeed', '8_WIND_GUST_SPEED'),
    ('8_WindSpeed', '8_WIND_SPEED'),
    ('Access_technology', 'ACCESS_TECHNOLOGY'),
    ('accMotion', 'ACC_MOTION'),
    ('Actuator', 'ACTUATOR'),
    ('adc_ch1', 'ADC_CH1'),
    ('adc_ch2', 'ADC_CH2'),
    ('adc_ch3', 'ADC_CH3'),
    ('adc_ch4', 'ADC_CH4'),
    ('airTemp', 'AIR_TEMPERATURE'),
    ('airtemperature', 'AIR_TEMPERATURE'),
    ('airTemperature', 'AIR_TEMPERATURE'),
    ('altitude', 'ALTITUDE'),
    ('Ana', 'ANA'),
    ('atmosphericpressure', 'ATMOSPHERIC_PRESSURE'),
    ('atmosphericPressure', 'ATMOSPHERIC_PRESSURE'),
    ('Average_current', 'AVERAGE_CURRENT'),
    ('average-flow-velocity0_0_m/s', 'AVERAGE_FLOW_VELOCITY_0_0_MS'),
    ('Average_voltage', 'AVERAGE_VOLTAGE'),
    ('Average_Voltage', 'AVERAGE_VOLTAGE'),
    ('Average_Wind_Speed_', 'AVERAGE_WIND_SPEED'),
    ('avgWindDegrees', 'AVERAGE_WIND_DEGREES'),
    ('barometricPressure', 'BAROMETRIC_PRESSURE'),
    ('batmv', 'BATTERY_MV'),
    ('battery', 'BATTERY'),
    ('Battery (A)', 'BATTERY_A'),
    ('battery (v)', 'BATTERY_V'),
    ('Battery (V)', 'BATTERY_V'),
    ('batteryVoltage', 'BATTERY_V'),
    ('battery-voltage_V', 'BATTERY_V'),
    ('Battery (W)', 'BATTERY_W'),
    ('Cable', 'CABLE'),
    ('charging-state', 'CHARGING_STATE'),
    ('Class', 'CLASS'),
    ('command', 'COMMAND'),
    ('conductivity', 'CONDUCTIVITY'),
    ('counterValue', 'COUNTER_VALUE'),
    ('current-flow-velocity0_0_m/s', 'CURRENT_FLOW_VELOCITY_0_0_MS'),
    ('depth', 'DEPTH'),
    ('Device', 'DEVICE'),
    ('DI0', 'DI_0'),
    ('DI1', 'DI_1'),
    ('direction', 'DIRECTION'),
    ('distance', 'DISTANCE'),
    ('down630', 'DOWN_630'),
    ('down800', 'DOWN_800'),
    ('EC', 'EC'),
    ('externalTemperature', 'EXTERNAL_TEMPERATURE'),
    ('fault', 'FAULT'),
    ('Fraud', 'FRAUD'),
    ('gnss', 'GNSS'),
    ('gustspeed', 'GUST_SPEED'),
    ('gustSpeed', 'GUST_SPEED'),
    ('header', 'HEADER'),
    ('Humi', 'HUMI'),--HUMITY?
    ('humidity', 'HUMIDITY'),
    ('Hygro', 'HYGRO'),
    ('Leak', 'LEAK'),
    ('linpar', 'LINPAR'),
    ('Max_current', 'MAXIMUM_CURRENT'),
    ('Maximum_Wind_Speed_', 'MAXIMUM_WIND_SPEED'),
    ('Max_voltage', 'MAXIMUM_VOLTAGE'),
    ('Min_current', 'MINIMUM_CURRENT'),
    ('Minimum_Wind_Speed_', 'MINIMUM_WIND_SPEED'),
    ('Min_voltage', 'MINIMUM_VOLTAGE'),
    ('moisture1', 'MOISTURE_1'),
    ('moisture2', 'MOISTURE_2'),
    ('moisture3', 'MOISTURE_3'),
    ('moisture4', 'MOISTURE_4'),
    ('ndvi', 'NDVI'),
    ('O06 / DPI-144', 'O06_DPI_144'),
    ('Operating_cycle', 'OPERATING_CYCLE'),
    ('packet-type', 'PACKET_TYPE'),
    ('period', 'PERIOD'),
    ('Power', 'POWER'),
    ('precipitation', 'PRECIPITATION'),
    ('pressure', 'PRESSURE'),
    ('Processor_temperature', 'PROCESSOR_TEMPERATURE'),
    ('pulse_count', 'PULSE_COUNT'),
    ('Radio_channel_code', 'RADIO_CHANNEL_CODE'),
    ('Rainfall', 'RAINFALL'),
    ('rain_per_interval', 'RAIN_PER_INTERVAL'),
    ('Rain_per_interval', 'RAIN_PER_INTERVAL'),
    ('raw_depth', 'RAW_DEPTH'),
    ('rawSpeedCount', 'RAWSPEEDCOUNT'),
    ('relativehumidity', 'RELATIVE_HUMIDITY'),
    ('relativeHumidity', 'RELATIVE_HUMIDITY'),
    ('Rest_capacity', 'REST_CAPACITY'),
    ('Rest_power', 'REST_POWER'),
    ('rssi', 'RSSI'),
    ('rtc', 'RTC'),
    ('RTC', 'RTC'),
    ('S1_EC', 'S1_EC'),
    ('S1_Temp', 'S1_TEMP'),
    ('S1_Temp_10cm', 'S1_TEMP_10_CM'),
    ('S1_Temp_20cm', 'S1_TEMP_20_CM'),
    ('S1_Temp_30cm', 'S1_TEMP_30_CM'),
    ('S1_Temp_40cm', 'S1_TEMP_40_CM'),
    ('S1_Temp_50cm', 'S1_TEMP_50_CM'),
    ('S1_Temp_60cm', 'S1_TEMP_60_CM'),
    ('S1_Temp_70cm', 'S1_TEMP_70_CM'),
    ('S1_Temp_80cm', 'S1_TEMP_80_CM'),
    ('S1_Temp_90cm', 'S1_TEMP_90_CM'),
    ('S1_VWC', 'S1_VWC'),
    ('s4solarRadiation', 'S4_SOLAR_RADIATION'),
    ('salinity', 'SALINITY'),
    ('salinity1', 'SALINITY_1'),
    ('salinity2', 'SALINITY_2'),
    ('salinity3', 'SALINITY_3'),
    ('salinity4', 'SALINITY_4'),
    ('sensorReading', 'SENSOR_READING'),
    ('shortest_pulse', 'SHORTEST_PULSE'),
    ('Signal', 'SIGNAL'),
    ('Signal_indication', 'SIGNAL_INDICATION'),
    ('Signal_strength', 'SIGNAL_STRENGTH'),
    ('snr', 'SNR'),
    ('soilmoist', 'SOIL_MOIST'),
    ('soiltemp', 'SOIL_TEMPERATURE'),
    ('solar', 'SOLAR'),
    ('Solar (A)', 'SOLAR_A'),
    ('solarpanel', 'SOLAR_PANEL'),
    ('solarPanel', 'SOLAR_PANEL'),
    ('solar (v)', 'SOLAR_V'),
    ('Solar (V)', 'SOLAR_V'),
    ('solar-voltage_V', 'SOLAR_V'),
    ('Solar (W)', 'SOLAR_W'),
    ('solmv', 'SOL_MV'),
    ('sq110_umol', 'SQ_110_UMOL'),
    ('strikes', 'STRIKES'),
    ('Tamper', 'TAMPER'),
    ('tdskcl', 'TDSKCL'),
    ('Temp', 'TEMPERATURE'),
    ('temperature', 'TEMPERATURE'),
    ('Temperature', 'TEMPERATURE'),
    ('temperature1', 'TEMPERATURE_1'),
    ('temperature2', 'TEMPERATURE_2'),
    ('temperature3', 'TEMPERATURE_3'),
    ('temperature4', 'TEMPERATURE_4'),
    ('temperature5', 'TEMPERATURE_5'),
    ('temperature6', 'TEMPERATURE_6'),
    ('temperature7', 'TEMPERATURE_7'),
    ('temperature8', 'TEMPERATURE_8'),
    ('temperatureReading', 'TEMPERATURE_READING'),
    ('tilt-anlge0_0_Degrees', 'TILT_ANLGE_0_0_DEGREES'),
    ('UNIX_time', 'UNIX_TIME'),
    ('up630', 'UP_630'),
    ('up800', 'UP_800'),
    ('uptime_s', 'UPTIME_S'),
    ('vapourpressure', 'VAPOUR_PRESSURE'),
    ('vapourPressure', 'VAPOUR_PRESSURE'),
    ('vdd', 'VDD'),
    ('Volt', 'V'),
    ('vt', 'VT'),
    ('VWC', 'VWC'),
    ('VWC1', 'VWC_1'),
    ('winddirection', 'WIND_DIRECTION'),
    ('windDirection', 'WIND_DIRECTION'),
    ('windKph', 'WIND_KPH'),
    ('windspeed', 'WIND_SPEED'),
    ('windSpeed', 'WIND_SPEED'),
    ('windStdDevDegrees', 'WIND_STANDARD_DEVIATION_DEGREES');


-- Enable the PostGIS extensions
-- CREATE EXTENSION postgis;
-- CREATE EXTENSION postgis_raster;
-- CREATE EXTENSION postgis_sfcgal;
