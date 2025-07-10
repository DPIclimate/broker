#  dpi-scmn-updateLookupTables updatelookup.py
#  Description:      Main file for project to write data into lookup tables from google sheets
#  Author:           Glen Charlton
#  Created:          11 April 2023
#  Source:           https://github.com/glencharlton/dpi-scmn-lookuptableupload/
#  License:          Copyright (c) 2020 Intersect Australia - All Rights Reserved
#                    Unauthorized copying of this file, via any medium is
#                    strictly prohibited. Proprietary and confidential
import os
from pathlib import Path

##### Libraries #####
import numpy as np
import pandas as pd
import gsheets
import psql

##### Parameters #####
SPREADSHEET_ID = os.environ['SPREADSHEET_ID']
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
DATA_TO_PULL = 'data entry'

_clear_cache_flag_file = Path(os.environ['CLEAR_CALIBRATION_CACHE_FILE'])


##### Functions #####

##### Main #####
#if __name__ == '__main__':

# Pull data from Google Sheets
data = gsheets.pull_sheet_data(SCOPES,SPREADSHEET_ID,DATA_TO_PULL)
df = pd.DataFrame(data[1:], columns=data[0])

# Extract database structure and sort table
schemas = df.iloc[1].values
tables = df.iloc[0].values
columns = df.columns

# Loop through each table
unique_tables = np.unique(tables)
for table in unique_tables:
    # define schema
    schema = schemas[np.where(tables == table)][0]
    # define extract and process table contents
    db_table = df.loc[2:, (df.iloc[0] == table) & (df.iloc[1] == schema)]
    db_table = db_table[db_table.iloc[:,0] != '']
    db_table = db_table.replace(r'^\s*$', None, regex=True)
    db_table = db_table.dropna(how='all')

    # write to database
    print(str('Updating Table: ' + schema + "." + table))
    con = psql.psql_connect()
    psql.psql_replace(con, db_table, str(schema + '.' + table))
    psql.psql_disconnect(con)

# Signal the message wrangling code to clear its calibration values cache.
_clear_cache_flag_file.touch(exist_ok=True)

print('Complete')
#end
