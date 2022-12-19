# Suite of tests to verify API functionality
import requests
import json
import jsonschema
from jsonschema import validate
import unittest

from app.utils.api import headers, sources_link_all, physical_link_all, logical_link_all, physical_link_notes, \
    physical_link_uid, logical_link_uid, logical_link_insert, mapping_link_all, mapping_link_current, \
    mapping_link_insert


# Declarations from the main api.py file, saves having to update test file if base API changes
sources_link_all_test = sources_link_all
physical_link_all_test = physical_link_all
physical_link_notes_test = physical_link_notes
logical_link_all_test = logical_link_all
physical_link_uid_test = physical_link_uid
logical_link_uid_test = logical_link_uid
logical_link_insert_test = logical_link_insert
mapping_link_all_test = mapping_link_all
mapping_link_current_test = mapping_link_current
mapping_link_insert_test = mapping_link_insert
api_header = headers

def get_schema():
    """This function loads the given schema available"""
    with open('logicalDeviceSchema.json', 'r') as file:
        schema = json.load(file)
    return schema

def validate_json(json_data):
    """REF: https://json-schema.org/ """
    execute_api_schema = get_schema()
    try:
        validate(instance=json_data, schema=execute_api_schema)
    except jsonschema.exceptions.ValidationError:
        return False
    return True


class TestAPI(unittest.TestCase):
    def test_get_sources(self):
        response_code = requests.get(sources_link_all, headers=headers).status_code
        self.assertEqual(response_code, 200)

    def test_get_physical_devices(self):
        response_code = requests.get(physical_link_all, headers=headers).status_code
        self.assertEqual(response_code, 200)

    def test_get_physical_notes(self):
        response_code = requests.get(physical_link_notes + '1', headers=headers).status_code
        self.assertEqual(response_code, 200)

    def test_get_logical_devices(self):
        response_code = requests.get(logical_link_all, headers=headers).status_code
        self.assertEqual(response_code, 200)

    def test_get_physical_device(self):
        response_code = requests.get(physical_link_uid + '1', headers=headers).status_code
        self.assertEqual(response_code, 200)

    def test_get_logical_device(self):
        response_code = requests.get(logical_link_uid + '1', headers=headers).status_code
        self.assertEqual(response_code, 200)

    def test_get_device_mappings(self):
        response_code = requests.get(mapping_link_all + '1', headers=headers).status_code
        self.assertEqual(response_code, 200)

    def test_get_device_mapping(self):
        response_code = requests.get(mapping_link_current + '2', headers=headers).status_code
        self.assertEqual(response_code, 200)

    def test_validate_logical_device_response(self):
        response = requests.get(logical_link_uid + '1', headers=headers)
        is_valid = validate_json(response.json())
        self.assertTrue(is_valid, 'Failed - Logical device response does not match schema')


