#
#
#implements an automated way to standardise incoming timeseries names to make data cleaner
#aims to eliminate the possibility of timeseries names changing over time if devices change
#
#

import re, os, time, logging
import api.client.DAO as dao


def update_data_structs():
    try:
        type_maps = dict(dao.get_type_map())
        word_list = dao.get_word_list()
        hash_table = dict(dao.get_hash_table())
        return type_maps, [item[0] for item in word_list], hash_table
    except Exception as e:
        logging.info("Error while updating word_list/type_map structures:", e)
        return {}, [], {"word_list":"", "type_name_map":""}


PULL_INTERVAL = int(os.environ.get('NAMING_UPDATE_INTERVAL', 600))
TYPE_MAPS, WORD_LIST, HASH_TABLE = update_data_structs()
HASH_TABLE = dict(dao.get_hash_table())
last_data_pull_time = 0


def check_and_update_structs():
    """
    atm the hash_table only has two rows, so pulling both at once and checking is probably
    better,
    if more hashes go in, then maybe redoing this to query database for just those two hashes
    """
    global last_data_pull_time
    global HASH_TABLE, WORD_LIST, TYPE_MAPS

    current_time = time.time()

    logging.info('in updates')

    if current_time - last_data_pull_time >= PULL_INTERVAL:
        logging.info('checking for updates')
        last_data_pull_time = time.time()
        try:
            new_hash_table = dict(dao.get_hash_table())
            if HASH_TABLE['word_list'] != new_hash_table['word_list']:
                word_list = dao.get_word_list()
                WORD_LIST = [item[0] for item in word_list]
                HASH_TABLE['word_list'] = new_hash_table['word_list']
            if HASH_TABLE['type_name_map'] != new_hash_table['type_name_map']:
                TYPE_MAPS = dict(dao.get_type_map())
                HASH_TABLE['type_name_map'] = new_hash_table['type_name_map']
        except:
            logging.error("unable to update naming structs")


def clean_name(msg: str) -> str:
    """
    strip special chars from beginning and end
    make upper case                                 --> ie aBcd                 => ABCD
    replace <space> and '-' with '_'                --> ie 1-2 3_4              => 1_2_3_4
    remove special characters except '_'            --> ie !2>_3                => 2_3
    remove duplicated '_'                           --> ie 1__2                 => 1_2
    separete all known words                        --> ie UPWINDVAPOUR         => UP_WIND_VAPOUR
    remove duplicate words                          --> ie BATTERY_VOLTAGE_V    => BATTERY_V
    normalise words                                 --> ie VOLTAGE              => V

    Additionally, table name must not start or end with the . character. 
    Column name must not contain . -
    """

    check_and_update_structs()

    special_characters = '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ '
    cleaned_name = separate_and_normalise_words(msg.upper().replace(" ", "_").replace("-","_"))
    cleaned_name = cleaned_name.lstrip(special_characters).rstrip(special_characters)
    cleaned_name = split_numbers_by_underscore(cleaned_name)
    cleaned_name = re.sub(r'[^\w\s]', '', cleaned_name)
    cleaned_name = re.sub(r'_+', '_', cleaned_name)

    return cleaned_name


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

    uses naming_constants.WORD_LIST

    also removes duplicates if the same words ie BATTERY_VOLTAGE_V => BATTERY_V_V => BATTERY_V
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
            words.append(normalise_word(found_word))
            i += len(found_word)
            start_index = i
        else:
            i += 1
    if i > start_index:
        words.extend(msg[start_index:i].split("_"))

    removed_duplicates = remove_duplicates(words)

    return "_".join(removed_duplicates)


def split_numbers_by_underscore(msg: str) -> str:
    """
    splits numbers by underscores
    
    a123b ==> 1_123_b
    """
    result = []
    prev_char = None

    for char in msg:
        if prev_char and char.isdigit() != prev_char.isdigit():
            result.append('_')
        result.append(char)
        prev_char = char

    return ''.join(result)


