import subprocess
import time
import unittest

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By

subprocess.Popen("main.py", shell=True)
driver = webdriver.Chrome('chromedriver.exe')
driver.get("http://127.0.0.1:5000")


# Function to highlight web elements, largely for debugging the auto-script
def highlight(element, effect_time, color, border):
    """Highlights (blinks) a Selenium Webdriver element"""
    driver = element._parent

    def apply_style(s):
        driver.execute_script("arguments[0].setAttribute('style', arguments[1]);",
                              element, s)

    original_style = element.get_attribute('style')
    apply_style("border: {0}px solid {1};".format(border, color))
    # Remove below comment to enable highlighting for debugging
    #time.sleep(effect_time)
    apply_style(original_style)


class TestUI(unittest.TestCase):

    def test_01_verify_physical_device_column_titles(self):
        index = 1
        expectedColumns = ["LAST SEEN", "SOURCE", "NAME", "UID"]
        while index < 5:
            columnPath = '#DataTables_Table_0 > thead > tr > th:nth-child(' + str(index) + ')'
            elem = driver.find_element(By.CSS_SELECTOR, columnPath)
            highlight(elem, 2, 'red', 5)
            columnText = elem.text
            index += 1
            self.assertEqual(expectedColumns.pop(), columnText)


    def test_02_verify_update_mapping_button_visible(self):
        """Verify the update mapping button has rendered"""
        elem = driver.find_element(By.XPATH, '//*[@id="physicalmappingbuttons"]/li[1]/span')
        buttonText = elem.get_attribute('innerText')
        highlight(elem, 2, 'red', 5)
        self.assertEqual(buttonText, 'UPDATE MAPPING')

    def test_03_verify_create_mapping_button_visible(self):
        """Verify the create mapping button has rendered"""
        elem = driver.find_element(By.XPATH, '//*[@id="physicalmappingbuttons"]/li[2]/span')
        buttonText = elem.get_attribute('innerText')
        highlight(elem, 2, 'red', 5)
        self.assertEqual(buttonText, 'CREATE MAPPING')

    def test_04_device_hyperlink(self):
        """Test to verify the hyperlinks to access device is working (checks the first device row)"""
        deviceLink = driver.find_element(By.XPATH, "//*[@id='DataTables_Table_0']/tbody/tr[1]/td[2]/a")
        highlight(deviceLink, 2, 'red', 5)
        deviceLink.click()
        browserURL = driver.current_url
        self.assertTrue('physical-device' in browserURL)

    def test_05_verify_physical_device_headings(self):
        pageHeading = driver.find_element(By.XPATH, "/html/body/section/h2")
        highlight(pageHeading, 2, 'red', 5)
        # Verify physical device page labels are present
        self.assertTrue('Physical Device 1' in pageHeading.text)
        # Verify form heading is visible
        elem = driver.find_element(By.XPATH, "//h3[@id='form-heading']")
        highlight(elem, 2, 'red', 5)
        formHeading = elem.text
        self.assertEqual(formHeading, 'Form')
        # Verify properties heading is visible
        elem = driver.find_element(By.XPATH, "//h3[@id='properties-heading']")
        highlight(elem, 2, 'red', 5)
        propertiesHeading = elem.text
        self.assertEqual(propertiesHeading, 'Properties')
        # Verify mapping heading is visible
        elem = driver.find_element(By.XPATH, "//h3[@id='mapping-heading']")
        highlight(elem, 2, 'red', 5)
        mappingHeading = elem.text
        self.assertEqual(mappingHeading, 'Mapping')
        # Verify notes heading is visible
        elem = driver.find_element(By.XPATH, "//h3[@id='notes-heading']")
        highlight(elem, 2, 'red', 5)
        notesHeading = elem.text
        self.assertEqual(notesHeading, 'Notes')

    def test_06_verify_form_labels(self):
        """Verify the labels are correct underneath the form heading"""
        index = 1
        expectedLabels = ["Location", "Source", "Name", "UID"]
        while index < 5:
            elem = driver.find_element(By.XPATH, "/html/body/section/div/div[1]/div[1]/form/div[" + str(
                index) + "]/label")
            highlight(elem, 2, 'red', 5)
            labelText = elem.text
            self.assertEqual(expectedLabels.pop(), labelText)
            index += 1

    def test_07_verify_mapping_column_titles(self):
        """Verify the column titles are correct underneath the mapping heading"""
        index = 1
        expectedColumns = ["End Time", "Start Time", "Device Name", "Device ID"]
        while index < 5:
            columnPath = '/html/body/section/div/div[2]/div[1]/table/thead/tr/th[' + str(index) + ']'
            elem = driver.find_element(By.XPATH, columnPath)
            highlight(elem, 2, 'red', 5)
            columnText = elem.text
            index += 1
            self.assertEqual(expectedColumns.pop(), columnText)


    def test_08_verify_notes_column_titles(self):
        """Verify the column titles are correct underneath the mapping heading"""
        index = 1
        expectedColumns = ["TIMESTAMP", "NAME"]
        while index < 3:
            columnPath = '//*[@id="DataTables_Table_0"]/thead/tr/th[' + str(index) + ']'
            elem = driver.find_element(By.XPATH, columnPath)
            highlight(elem, 2, 'red', 5)
            columnText = elem.text
            index += 1
            self.assertEqual(expectedColumns.pop(), columnText)


    def test_09_verify_physical_device_banner_button_visible(self):
        button = driver.find_element(By.XPATH, '//*[@id="physical-device-banner-heading"]')
        highlight(button, 2, 'red', 5)
        self.assertTrue(button.is_displayed)

    def test_10_verify_logical_device_banner_button_visible(self):
        button = driver.find_element(By.XPATH, '//*[@id="logical-device-banner-heading"]')
        highlight(button, 2, 'red', 5)
        self.assertTrue(button.is_displayed)

    def test_11_check_banner_buttons_visible(self):
        expectedButtons = ["ADD NOTE", "CREATE MAPPING", 'UPDATE MAPPING', 'SAVE']
        index = 1
        while index < 5:
            button = driver.find_element(By.XPATH, '/html/body/div/div/ul/li['+ str(index) +']')
            buttonText = button.text
            highlight(button, 2, 'red', 5)
            index +=1
            self.assertEqual(expectedButtons.pop(), buttonText)

    def test_12_check_header_title(self):
        headerTitle = driver.find_element(By.XPATH, '//*[@id="header-title"]')
        highlight(headerTitle, 2, 'red', 5)
        self.assertEqual(headerTitle.text, 'DPI | Device Manager')

    def test_13_form_data_validation(self):
        """Test to validate that the page is displaying valid data"""
        physical_device_base_api = 'https://staging.farmdecisiontech.net.au/broker/api/physical/devices/'
        headers = {"Authorization": "Bearer bad_token"}
        response = requests.get(physical_device_base_api + '1', headers=headers).json()
        devicename = response['name']
        formText = driver.find_element(By.XPATH, '//*[@id="form-device-name"]').get_attribute('value')
        self.assertEqual(devicename, formText)

        sourcename = response['source_name']
        self.assertEqual(sourcename, driver.find_element(By.XPATH, '//*[@id="form-source"]').get_attribute('value'))

        lastseen = response['last_seen']
        lastseentext = driver.find_element(By.XPATH, '//*[@id="device-last-seen"]').get_attribute('value')
        self.assertEqual(lastseen, lastseentext)

