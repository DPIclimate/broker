#generate a large number of messages
#with somewhat realistic values, based off the iota.sql back up file

import random
import sys
from datetime import datetime, timedelta

random.seed(999)


NUM_OF_UID = 1000
NUM_OF_TS_PER_UID = 100
START_DATE = datetime(2023,1,1)
TIME_SERIES_NAMES = [
    ("1_Temperature", float),
    ("1_VWC", float),
    ("2_Temperature", float),
    ("2_VWC", float),
    ("3_Temperature", float),
    ("3_VWC", float),
    ("4_Temperature", float),
    ("4_VWC", float),
    ("5_Temperature", float),
    ("5_VWC", float),
    ("6_Temperature", float),
    ("6_VWC", float),
    ("8_AirPressure", float),
    ("8_AirTemperature", float),
    ("8_HumiditySensorTemperature", float),
    ("8_Precipitation", float),
    ("8_RH", float),
    ("8_Solar", float),
    ("8_Strikes", float),
    ("8_VaporPressure", float),
    ("8_WindDirection", float),
    ("8_WindGustSpeed", float),
    ("8_WindSpeed", float),
    ("Access_technology", float),
    ("accMotion", float),
    ("Actuator", float),
    ("adc_ch1", int),
    ("adc_ch2", int),
    ("adc_ch3", int),
    ("adc_ch4", int),
    ("airTemp", float),
    ("airtemperature", float),
    ("airTemperature", float),
    ("altitude", float),
    ("Ana", float),
    ("atmosphericpressure", float),
    ("atmosphericPressure", float),
    ("Average_current", float),
    ("average-flow-velocity0_0_m/s", float),
    ("Average_voltage", float),
    ("Average_Voltage", float),
    ("Average_Wind_Speed_", float),
    ("avgWindDegrees", int),
    ("barometricPressure", float),
    ("batmv", float),
    ("battery", float),
    ("Battery (A)", float),
    ("battery (v)", float),
    ("Battery (V)", float),
    ("batteryVoltage", float),
    ("battery-voltage_V", float),
    ("Battery (W)", float),
    ("Cable", float),
    ("charging-state", float),
    ("Class", float),
    ("command", float),
    ("conductivity", int),
    ("counterValue", float),
    ("current-flow-velocity0_0_m/s", float),
    ("depth", float),
    ("Device", float),
    ("DI0", float),
    ("DI1", float),
    ("direction", float),
    ("distance", float),
    ("down630", float),
    ("down800", float),
    ("EC", int),
    ("externalTemperature", float),
    ("fault", float),
    ("Fraud", float),
    ("gnss", float),
    ("gustspeed", float),
    ("gustSpeed", float),
    ("header", float),
    ("Humi", float),
    ("humidity", float),
    ("Hygro", float),
    ("Leak", float),
    ("linpar", float),
    ("Max_current", float),
    ("Maximum_Wind_Speed_", float),
    ("Max_voltage", float),
    ("Min_current", float),
    ("Minimum_Wind_Speed_", float),
    ("Min_voltage", float),
    ("moisture1", float),
    ("moisture2", float),
    ("moisture3", float),
    ("moisture4", float),
    ("ndvi", float),
    ("O06 / DPI-144", float),
    ("Operating_cycle", float),
    ("packet-type", float),
    ("period", float),
    ("Power", float),
    ("precipitation", float),
    ("pressure", float),
    ("Processor_temperature", float),
    ("pulse_count", float),
    ("Radio_channel_code", float),
    ("Rainfall", float),
    ("rain_per_interval", float),
    ("Rain_per_interval", float),
    ("raw_depth", int),
    ("rawSpeedCount", int),
    ("relativehumidity", float),
    ("relativeHumidity", float),
    ("Rest_capacity", float),
    ("Rest_power", float),
    ("rssi", float),
    ("rtc", int),
    ("RTC", int),
    ("S1_EC", float),
    ("S1_Temp", float),
    ("S1_Temp_10cm", float),
    ("S1_Temp_20cm", float),
    ("S1_Temp_30cm", float),
    ("S1_Temp_40cm", float),
    ("S1_Temp_50cm", float),
    ("S1_Temp_60cm", float),
    ("S1_Temp_70cm", float),
    ("S1_Temp_80cm", float),
    ("S1_Temp_90cm", float),
    ("S1_VWC", float),
    ("s4solarRadiation", float),
    ("salinity", float),
    ("salinity1", float),
    ("salinity2", float),
    ("salinity3", float),
    ("salinity4", float),
    ("sensorReading", float),
    ("shortest_pulse", float),
    ("Signal", float),
    ("Signal_indication", float),
    ("Signal_strength", float),
    ("snr", float),
    ("soilmoist", float),
    ("soiltemp", float),
    ("solar", float),
    ("Solar (A)", float),
    ("solarpanel", float),
    ("solarPanel", float),
    ("solar (v)", float),
    ("Solar (V)", float),
    ("solar-voltage_V", float),
    ("Solar (W)", float),
    ("solmv", int),
    ("sq110_umol", float),
    ("strikes", float),
    ("Tamper", float),
    ("tdskcl", int),
    ("Temp", float),
    ("temperature", float),
    ("Temperature", float),
    ("temperature1", float),
    ("temperature2", float),
    ("temperature3", float),
    ("temperature4", float),
    ("temperature5", float),
    ("temperature6", float),
    ("temperature7", float),
    ("temperature8", float),
    ("temperatureReading", float),
    ("tilt-anlge0_0_Degrees", float),
    ("UNIX_time", float),
    ("up630", float),
    ("up800", float),
    ("uptime_s", float),
    ("vapourpressure", float),
    ("vapourPressure", float),
    ("vdd", int),
    ("Volt", float),
    ("vt", int),
    ("VWC", int),
    ("VWC1", int),
    ("winddirection", float),
    ("windDirection", int),
    ("windKph", float),
    ("windspeed", float),
    ("windSpeed", float),
    ("windStdDevDegrees", float)
]


RANDOM_FLOATS = [random.uniform(0,30) for _ in range(1000)]
RANDOM_INTS = [random.uniform(0,10000) for _ in range(1000)]

int_counter = 0
float_counter = 0

#easier set of how many tests:
#python generate_messages.py 100 100 > msgs
#would give 100 uids (0-99) and each would have 100 lots of time series data
if len(sys.argv)==2:
    NUM_OF_UID=int(sys.argv[1])
elif len(sys.argv)==3:
    NUM_OF_UID=int(sys.argv[1])
    NUM_OF_TS_PER_UID=int(sys.argv[2])


for uid in range(NUM_OF_UID):
    random_names = random.choices(TIME_SERIES_NAMES, k=random.randint(1,10))
    START_DATE = START_DATE + timedelta(hours=1)
    for i in range(NUM_OF_TS_PER_UID):
        ts = START_DATE + timedelta(hours=i)
        ts_str = ts.isoformat(timespec='microseconds') + 'Z'
        message = f'{{"broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6", "l_uid": {uid}, "p_uid": {uid}, "timestamp":"{ts_str}", "timeseries": ['
        for idx, (name,dt) in enumerate(random_names):
            if dt == float:
                message += f'{{"name": "{name}", "value": {RANDOM_FLOATS[float_counter]}'
                float_counter = (float_counter + 1) % len(RANDOM_FLOATS)
            else:
                message += f'{{"name": "{name}", "value": {RANDOM_INTS[float_counter]}'
                int_counter = (int_counter + 1) % len(RANDOM_INTS)
            if idx < len(random_names) - 1:
                message += "}, "
        print(message + "}]}")
