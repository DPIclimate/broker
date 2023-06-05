# Scenario 1: Send a message to the output service

## Scenario Description

The purpose of this test is to confirm the primary functionality of the
output service works as intended.

> There is only one Test scenario for this purpose following:

- The output service receives a message from RabbitMQ.

## Version Control

| Version \# | Date       | Author     | Description                      |
|------------|------------|------------|----------------------------------|
| 0.1        | 23/05/2023 | Zak        | Initial Draft                    |
| 1.0        | 01/06/2023 | Zak        | Initial Version                  |
| 1.1        | 04/06/2023 | Whole Team | Added test run links for images. |

## Test Scripts

The following scripts will cover this scenario:

- 1.1 Send a valid message

- 1.2 Send an invalid message

- 1.3 Send a valid message following an invalid message

## Use Cases

- The output service receives a message from RabbitMQ.

- The output service extracts the data points from the message.

- The output service stores the data points in the time series database.

## Test Components/Requirements

This test scenario covers the following high-level test requirements
(see scripts below for specific requirements covered by each test
script):

- The output service should never fail to insert data from a valid
  message.

- The output service should not insert data from invalid messages.

- The output service must never fail to receive a message.

## User Groups

- DPI staff

## Script Guide:

## Startup the Docker-Compose Stack:

Run the Docker-compose stack using the run.sh file within the main repo
directory, specifying the test environment.

This will require Docker-compose to be set up in your Linux environment.

## Send a Message:

The way to send a message to the database manually involves a few steps.

1.  Access the RabbitMQ Management console via a browser using the
    address:  
    [<u>http://localhost:15672/#/queues/%2F/ltsreader_logical_msg_queue</u>](http://localhost:15672/#/queues/%2F/ltsreader_logical_msg_queue)

2.  Login with the username: “broker” and password: “CHANGEME”

3.  Click on publish message, and paste a json message into the payload
    section, then publish it.

    1.  example message:

> {
>
> "broker_correlation_id": "4798124-3094032",
>
> "p_uid": 101,
>
> "l_uid": 102,
>
> "timestamp": "2023-04-21T10:45:00Z",
>
> "timeseries": \[
>
> {
>
> "name": "Test Type",
>
> "value": "Valid UAT"
>
> }
>
> \]
>
> }

4.  The listener should receive the message and process it, to verify
    whether it was added or not, perform data retrieval.

## Data Retrieval:

Each database has a specific process to retrieve data due to lack of an
API at this time:

|                |                                                                                                                                                                                                                |
|----------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Database:**  | **Steps:**                                                                                                                                                                                                     |
| **Timescale**  | Run the retrieve_data.sh located in the 303/timescale-testing/ folder.                                                                                                                                         |
| **QuestDB**    | GOTO: [<u>http://localhost:9000/</u>](http://localhost:9000/) and run ‘dpi;’ to show data in database                                                                                                          |
| **InfluxDB**   | GOTO: [<u>http://localhost:8086/</u>](http://localhost:8086/) and go to Data Explorer in side bar - select bucket DPI, filter by \_measurement and select, view by table, hit submit to show data in database. |
| **Prometheus** | GOTO: http:localhost:9090/ and run ‘sensor_value’ to show scraped data for that instance, change timestamp to show data scraped earlier. (Note: Prometheus does not support the historical display of data)    |

## Data Wipe:

Databases below will need manual cleanup of data, the others should
automatically be cleared upon next startup of the Docker-Compose Stack.

|               |                                                                                                |
|---------------|------------------------------------------------------------------------------------------------|
| **Database:** | **Steps:**                                                                                     |
| **Timescale** | Run the clear_database.sh located in the 303/timescale-testing/ folder.                        |
| **QuestDB**   | via web console, run ‘drop table dpi;’ [<u>http://localhost:9000/</u>](http://localhost:9000/) |


## Script 1.1: Send a valid message

### Script Description

- Send a message from RabbitMQ to the logical time series queue.

- Confirm a message was stored in the database.

### Testing Requirements

This test script covers the following specific testing requirements:

- The output service should never fail to insert data from a valid
  message.

- The output service must never fail to receive a message.

### Setup

- Start the docker compose stack using “run.sh test”, and let all
  containers properly startup.

- Copy a valid message to RabbitMQ, for example:

> *{*
>
> *"broker_correlation_id": "4798124-3094032",*
>
> *"p_uid": 101,*
>
> *"l_uid": 102,*
>
> *"timestamp": "2023-04-21T10:45:00Z",*
>
> *"timeseries": \[*
>
> *{*
>
> *"name": "Test Type",*
>
> *"value": "Valid UAT"*
>
> *}*
>
> *\]*
>
> *}*

### Teardown

- Stop the docker compose stack, and remove any trace of DB storage if
  necessary.

### Script Steps

| **Step \#** | **Test Action**                                              | **Expected Results**                                                       | **Pass/ Fail** |
|-------------|--------------------------------------------------------------|----------------------------------------------------------------------------|----------------|
| 1           | Send a valid message to the queue using RabbitMQ Management. | Output service accepts the message, and saves the data points to the TSDB. | P              |
| 2           | Retrieve data from the database.                             | All data within the message is returned.                                   | P              |

### Test Execution

<table>
<colgroup>
<col style="width: 21%" />
<col style="width: 15%" />
<col style="width: 20%" />
<col style="width: 20%" />
<col style="width: 11%" />
<col style="width: 10%" />
</colgroup>
<thead>
<tr class="header">
<th>Date/Time</th>
<th>Tester</th>
<th>Test ID</th>
<th>Test Phase</th>
<th>Images</th>
<th>Status</th>
</tr>
</thead>
<tbody>
<tr class="odd">
<td>01/06/23 7:01 pm</td>
<td>Zak</td>
<td>Timescale1</td>
<td>System Cycle 1</td>
<td><p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/TIMESCALE_UAT_1_1A.png?raw=true"><u>Publish</u></a></p>
<p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/TIMESCALE_UAT_1_1B.png?raw=true"><u>Confirm</u></a></p></td>
<td>Passed</td>
</tr>
<tr class="even">
<td>03/06/23 4:21 pm</td>
<td>Cal</td>
<td>QuestDB1</td>
<td>System Cycle 1</td>
<td><a
href="https://raw.githubusercontent.com/ZakhaevK/itc303-team3-broker/master/303/tests/UAT/QUSTDB_UAT_1_1.png"><u>Link</u></a></td>
<td>Passed</td>
</tr>
<tr class="odd">
<td>04/06/23 5:03pm</td>
<td>Sara</td>
<td>InfluxDB1</td>
<td>System Cycle 1</td>
<td><p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/INFLUXDB_UAT_1_1A.png"><u>Publish</u></a></p>
<p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/INFLUXDB_UAT_1_1B.png"><u>Confirm</u></a></p></td>
<td>Passed</td>
</tr>
<tr class="even">
<td>04/06/23 7:55pm</td>
<td>Rishabh</td>
<td>PromDB1</td>
<td>System Cycle 1</td>
<td><p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/PROMDB_UAT_1_1A.png"><u>Step
1</u></a></p>
<p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/PROMDB_UAT_1_1B.png"><u>Step
2</u></a></p></td>
<td>Passed</td>
</tr>
</tbody>
</table>

##  

## Script 1.2: Send an invalid message

### Script Description

- Send an invalid message from RabbitMQ to the logical time series
  queue.

- Confirm a message was not stored in the database.

### Testing Requirements

This test script covers the following specific testing requirements:

- The output service should not insert data from invalid messages.

- The output service must never fail to receive a message.

### Setup

- Start the docker compose stack using “run.sh”, and let all containers
  properly startup.

- Copy an valid message to RabbitMQ, for example:

> *{*
>
> *"borked_correlation_id": "420",*
>
> *"p_uid": 999,*
>
> *"l_uid": 999,*
>
> *"timestamp": "2023-04-21T10:45:00Z",*
>
> *"timeseries": \[*
>
> *{*
>
> *"name": "Test Type",*
>
> *"value": "Invalid UAT"*
>
> *}*
>
> *\]*
>
> *}*

### Teardown

- Stop the docker compose stack, and remove any other trace of DB
  storage if necessary.

### Script Steps

| **Step \#** | **Test Action**                                                 | **Expected Results**                                                | **Pass/ Fail** |
|-------------|-----------------------------------------------------------------|---------------------------------------------------------------------|----------------|
| 1           | Send an invalid message to the queue using RabbitMQ Management. | Output service accepts message, but does not store the data points. | P              |
| 2           | Retrieve data from the database.                                | No data is returned.                                                | P              |

### 

### Test Execution

<table>
<colgroup>
<col style="width: 21%" />
<col style="width: 16%" />
<col style="width: 19%" />
<col style="width: 20%" />
<col style="width: 11%" />
<col style="width: 10%" />
</colgroup>
<thead>
<tr class="header">
<th>Date/Time</th>
<th>Tester</th>
<th>Test ID</th>
<th>Test Phase</th>
<th>Images</th>
<th>Status</th>
</tr>
</thead>
<tbody>
<tr class="odd">
<td>01/06/23 6:58 pm</td>
<td>Zak</td>
<td>Timescale1</td>
<td>System Cycle 1</td>
<td><p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/TIMESCALE_UAT_1_2A.png?raw=true"><u>Publish</u></a></p>
<p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/TIMESCALE_UAT_1_2B.png?raw=true"><u>Confirm</u></a></p></td>
<td>Passed</td>
</tr>
<tr class="even">
<td>03/06/23 4:45 pm</td>
<td>Cal</td>
<td>QuestDB1</td>
<td>System Cycle 1</td>
<td><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/QUESTDB_UAT_1_2.png?raw=true"><u>Link</u></a></td>
<td>Passed</td>
</tr>
<tr class="odd">
<td>04/06/23 5:16 pm</td>
<td>Sara</td>
<td>InfluxDB1</td>
<td>System Cycle 2</td>
<td><p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/INFLUXDB_UAT_1_2A.png"><u>Publish</u></a></p>
<p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/INFLUXDB_UAT_1_2C.png"><u>Confirm</u></a></p></td>
<td>Passed</td>
</tr>
<tr class="even">
<td>04/06/23 10:15pm</td>
<td>Rishabh</td>
<td>PromDB1</td>
<td>System Cycle 1</td>
<td><p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/PROMDB_UAT_1_2A.png"><u>Step
1</u></a></p>
<p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/PROMDB_UAT_1_2B.png"><u>Step
2</u></a></p></td>
<td>Passed</td>
</tr>
</tbody>
</table>

## Script 1.3: Send a valid message following an invalid message

### Script Description

- Send an invalid message from RabbitMQ to the logical time series
  queue.

- Confirm a message was not stored in the database.

- Send a valid message from RabbitMQ to the logical time series queue.

- Confirm a message was stored in the database.

### Testing Requirements

This test script covers the following specific testing requirements:

- The output service should not insert data from invalid messages.

- The output service must never fail to receive a message.

- The output service should never fail to insert data from a valid
  message.

### Setup

- Start the docker compose stack using “run.sh”, and let all containers
  properly startup.

- Copy an Invalid Message to RabbitMQ, for example:

> *{*
>
> *"borked_correlation_id": "420",*
>
> *"p_uid": 999,*
>
> *"l_uid": 999,*
>
> *"timestamp": "2023-04-21T10:45:00Z",*
>
> *"timeseries": \[*
>
> *{*
>
> *"name": "Test Type",*
>
> *"value": "Invalid UAT"*
>
> *}*
>
> *\]*
>
> *}*

- Copy a valid Message to RabbitMQ, for example:

> {
>
> "broker_correlation_id": "4798124-3094032",
>
> "p_uid": 101,
>
> "l_uid": 102,
>
> "timestamp": "2023-04-21T10:45:00Z",
>
> "timeseries": \[
>
> {
>
> "name": "Test Type",
>
> "value": "Valid UAT"
>
> }
>
> \]
>
> }

### Teardown

- Stop the docker compose stack, and remove any trace of DB storage if
  necessary.

### Script Steps

| **Step \#** | **Test Action**                                                 | **Expected Results**                                                   | **Pass/ Fail** |
|-------------|-----------------------------------------------------------------|------------------------------------------------------------------------|----------------|
| 1           | Send an invalid message to the queue using RabbitMQ Management. | Output service accepts message, but does not store the data points.    | P              |
| 2           | Retrieve data from the database.                                | No data is returned.                                                   | P              |
| 3           | Send a valid message to the queue using RabbitMQ Management.    | Output service accepts message, and saves the data points to the TSDB. | P              |
| 4           | Retrieve data from the database.                                | All data within the valid message is returned.                         | P              |

### Test Execution

<table>
<colgroup>
<col style="width: 21%" />
<col style="width: 16%" />
<col style="width: 19%" />
<col style="width: 20%" />
<col style="width: 11%" />
<col style="width: 10%" />
</colgroup>
<thead>
<tr class="header">
<th>Date/Time</th>
<th>Tester</th>
<th>Test ID</th>
<th>Test Phase</th>
<th>Images</th>
<th>Status</th>
</tr>
</thead>
<tbody>
<tr class="odd">
<td>01/06/23 6:55 pm</td>
<td>Zak</td>
<td>Timescale1</td>
<td>System Cycle 1</td>
<td><p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/TIMESCALE_UAT_1_3A.png?raw=true"><u>Invalid</u></a></p>
<p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/TIMESCALE_UAT_1_3B.png?raw=true"><u>Invalid</u></a></p>
<p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/TIMESCALE_UAT_1_3C.png?raw=true"><u>Valid</u></a></p>
<p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/TIMESCALE_UAT_1_3D.png?raw=true"><u>Valid</u></a></p></td>
<td>Passed</td>
</tr>
<tr class="even">
<td>03/06/23 4:48 pm</td>
<td>Cal</td>
<td>QuestDB1</td>
<td>System Cycle 1</td>
<td><p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/QUESTDB_UAT_1_3A.png?raw=true"><u>Invalid</u></a></p>
<p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/QUESTDB_UAT1_3B.png?raw=true"><u>Valid</u></a></p></td>
<td>Passed</td>
</tr>
<tr class="odd">
<td>04/06/23 5:30 pm</td>
<td>Sara</td>
<td>InfluxDB1</td>
<td>System Cycle 1</td>
<td><p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/INFLUXDB_UAT_1_3a.png"><u>Invalid</u></a></p>
<p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/INFLUXDB_UAT_1_3C.png"><u>Invalid</u></a></p>
<p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/INFLUXDB_UAT_1_3D.png"><u>Valid</u></a></p>
<p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/INFLUXDB_UAT_1_3F.png"><u>Valid</u></a></p></td>
<td>Passed</td>
</tr>
<tr class="even">
<td>04/06/23 10:30pm</td>
<td>Rishabh</td>
<td>PromDB1</td>
<td>System Cycle 1</td>
<td><p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/PROMDB_UAT_1_3A.png"><u>Step
1</u></a></p>
<p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/PROMDB_UAT_1_3B.png"><u>Step
2</u></a></p>
<p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/PROMDB_UAT_1_3C.png"><u>Step
3</u></a></p>
<p><a
href="https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/PROMDB_UAT_1_3D.png"><u>Step
4</u></a></p></td>
<td>Passed</td>
</tr>
</tbody>
</table>
