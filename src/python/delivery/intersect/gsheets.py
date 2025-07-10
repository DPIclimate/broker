#  dpi-scmn-updateLookupTables main.py
#  Description:      File containing functions for Google Sheets for project to write data into lookup tables from google sheets
#  Author:           Glen Charlton
#  Created:          11 April 2023
#  Source:           https://github.com/glencharlton/dpi-scmn-lookuptableupload/
#  License:          Copyright (c) 2020 Intersect Australia - All Rights Reserved
#                    Unauthorized copying of this file, via any medium is
#                    strictly prohibited. Proprietary and confidential

import os.path
##### Libraries #####
from pathlib import Path
import pickle

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

_creds_file = Path(__file__).parent / 'credentials.json'
_token_file = Path(__file__).parent / 'token.pickle'

##### Function for checking/connecting to API #####
def gsheet_api_check(SCOPES):
    creds = None
    if os.path.exists(_token_file):
        with open(_token_file, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(_creds_file, SCOPES)
            creds = flow.run_local_server(port=0)
            with open(_token_file, 'wb') as token:
                pickle.dump(creds, token)
    return creds

##### function for pulling google sheet into pandas dataframe #####
def pull_sheet_data(SCOPES, SPREADSHEET_ID, DATA_TO_PULL):
    creds = gsheet_api_check(SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=DATA_TO_PULL).execute()
    values = result.get('values', [])

    if not values:
        print('No data found.')
    else:
        rows = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                  range=DATA_TO_PULL).execute()
        data = rows.get('values')
        print("Data Successfully Extracted from Google Sheet")
        return data
