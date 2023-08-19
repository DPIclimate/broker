import re
#WORDS THAT WOULD BE CHANGED TO TRY STANDARDISE
TYPE_MAPS = {
    "AMP": "A",
    "AMPERAGE":"A",
    "AMPS":"A",
    "VOLT":"V",
    "VOLTAGE":"V",
    "VOLTS":"V",
    "MAXIMUM":"MAX",
    "MINIMUM":"MIN",
    "CENTIMETER":"CM",
    "CENTIMETRE":"CM",
    "CENTIMETERS":"CM",
    "CENTIMETRES":"CM",
    "TEMP":"TEMPERATURE",
    "AVG":"AVERAGE",
    "MOIST":"MOISTURE"
}

#ADD WORDS THAT NEED TO BE SEPARATED
WORD_LIST = [
    "ACCESS",
    "ACTUATOR",
    "AIR",
    "ALTITUDE",
    "AMP",
    "AMPERAGE",
    "AMPS",
    "ATMOSPHERIC",
    "AVERAGE",
    "AVG",
    "BAROMETRIC",
    "BATTERY",
    "CABLE",
    "CAPACITY",
    "CHANNEL",
    "CHARGING",
    "CLASS",
    "CODE",
    "COMMAND",
    "CONDUCTIVITY",
    "COUNT",
    "COUNTER",
    "CURRENT",
    "CYCLE",
    "DEGREES",
    "DEPTH",
    "DEV",
    "DEVICE",
    "DISTANCE",
    "DIRECTION",
    "DOWN",
    "EXTERNAL",
    "FLOW",
    "FRAUD",
    "GUST",
    "HEADER",
    "HUMIDITY",
    "HYGRO",
    "INDICATION",
    "INTERVAL",
    "KPH",
    "LEAK",
    "MAX",
    "MAXIMUM",
    "MIN",
    "MINIMUM",
    "MOIST",
    "MOISTURE",
    "MOTION",
    "OPERATING",
    "PACKET",
    "PANEL",
    "PER",
    "PERIOD",
    "POWER",
    "PRECIPITATION",
    "PRESSURE",
    "PROCESSOR",
    "PULSE",
    "RADIO",
    "RAINFALL",
    "RAIN",
    "READING",
    "RELATIVE",
    "REST",
    "SALINITY",
    "SIGNAL",
    "SOLAR",
    "SOIL",
    "SPEED",
    "STRENGTH",
    "STRIKE",
    "STRIKES",
    "STD",
    "TECHNOLOGY",
    "TILT",
    "TIME",
    "UNIX",
    "UP",
    "UPTIME",
    "VALUE",
    "VAPOR",
    "VELOCITY",
    "VOLT",
    "VOLTS",
    "VOLTAGE",
    "READING",
    "SHORTEST",
    "SNR",
    "SOIL",
    "TAMPER",
    "TILT",
    "TIME",
    "TEMPERATURE",
    "TEMP",
    "UNIX",
    "UP",
    "VAPOUR",
    "WIND"
]

def normalise_word(word: str) -> str:
    """
    USES THE TYPE MAPS TO ALTER THE WORD TO A STANDARD FORMAT

    IE VOLTAGE, VOLT => V
    OR TEMP => TEMPERATURE
    """
    for type_word, symbol in TYPE_MAPS.items():
        pattern = r'\b' + re.escape(type_word) + r'\b'
        word = re.sub(pattern, symbol, word)
    return word


def remove_duplicates(words: list) -> list:
    """
        REMOVES ANY DUPLICATE WORDS IN LIST, NUMBERS ARE IGNORED

        prevents BATTERY_VOLTAGE_V from being BATTERY_V_V
    """
    processed_words = []
    for word in words:
        if word in processed_words and not word.isnumeric():
            continue
        processed_words.append(word)
    return processed_words



def separate_and_normalise_words(msg: str) -> str:
    """
    separates words (largest) by underscores based off ./naming_constants.py
    ie 1temperaturevoltagegggcurrent => 1_temperature_voltage_ggg_current

    uses naming_constants.word_list
    """
    words = []
    i = 0
    start_index = 0
    while i < len(msg):
        found_word = ""
        for word in WORD_LIST:
            if msg.startswith(word, i) and len(word) > len(found_word):
                found_word = word
        if found_word:
            if i > start_index:
                words.extend(msg[start_index:i].split("_"))
                #words.append(normalise_word(msg[start_index:i]))
            words.append(normalise_word(found_word))
            i += len(found_word)
            start_index = i
        else:
            i += 1
    if i > start_index:
        words.extend(msg[start_index:i].split("_"))
        #words.append(normalise_word(msg[start_index:i]))

    removed_duplicates = remove_duplicates(words)

    return "_".join(removed_duplicates)


def split_numbers_by_underscore(msg: str) -> str:
    result = []
    prev_char = None

    for char in msg:
        if prev_char and char.isdigit() != prev_char.isdigit():
            result.append('_')
        result.append(char)
        prev_char = char

    return ''.join(result)


