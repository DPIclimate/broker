**IoTa Time series Database**

**Test Scenario #1: Send a message to the output service**
#
## **Scenario 1: Send a message to the output service**
## <a name="_heading=h.gjdgxs"></a>**Scenario Description**
The purpose of this test is to confirm the primary functionality of the output service works as intended.

There is only one Test scenario for this purpose following:

- The output service receives a message from RabbitMQ.
## <a name="_heading=h.30j0zll"></a>**Version Control**

|**Version #**|**Date**|**Author**|**Description**|
| :- | :- | :- | :- |
|0\.1|23/05/2023|Zak|Initial Draft|
|1\.0|01/06/2023|Zak|Initial Version|
|1\.1|04/06/2023|Whole Team|Added test run links for images.|
## **Test Scripts**
The following scripts will cover this scenario:

- 1.1 Send a valid message
- 1.2 Send an invalid message
- 1.3 Send a valid message following an invalid message
## <a name="_heading=h.1fob9te"></a>**Use Cases**
- The output service receives a message from RabbitMQ.
- The output service extracts the data points from the message.
- The output service stores the data points in the time series database.
## **Test Components/Requirements**
This test scenario covers the following high-level test requirements (see scripts below for specific requirements covered by each test script):

- The output service should never fail to insert data from a valid message.
- The output service should not insert data from invalid messages.
- The output service must never fail to receive a message. 
## <a name="_heading=h.3znysh7"></a>**User Groups**
- DPI staff



## **Script Guide:**
## <a name="_heading=h.fn1a7mvd14v3"></a>**Startup the Docker-Compose Stack:**
Run the Docker-compose stack using the run.sh file within the main repo directory, specifying the test environment.

This will require Docker-compose to be set up in your Linux environment.
## <a name="_heading=h.c363s57whguo"></a>**Send a Message:**
The way to send a message to the database manually involves a few steps.

1. Access the RabbitMQ Management console via a browser using the address: 
   <http://localhost:15672/#/queues/%2F/ltsreader_logical_msg_queue> 
1. Login with the username: “broker” and password: “CHANGEME”
1. Click on publish message, and paste a json message into the payload section, then publish it.
   1. example message:

{

`  `"broker\_correlation\_id": "4798124-3094032",

`  `"p\_uid": 101,

`  `"l\_uid": 102,

`  `"timestamp": "2023-04-21T10:45:00Z",

`  `"timeseries": [

`	`{

`  	`"name": "Test Type",

`  	`"value": "Valid UAT"

`	`}

`  `]

}

1. The listener should receive the message and process it, to verify whether it was added or not, perform data retrieval.
## <a name="_heading=h.yax4w2gkpb2c"></a>**Data Retrieval:**
Each database has a specific process to retrieve data due to lack of an API at this time:

|**Database:**|**Steps:**|
| :- | :- |
|**Timescale**|Run the retrieve\_data.sh located in the 303/timescale-testing/ folder.|
|**QuestDB**|GOTO: <http://localhost:9000/> and run ‘dpi;’ to show data in database|
|**InfluxDB**|GOTO: <http://localhost:8086/> and go to Data Explorer in side bar - select bucket DPI, filter by \_measurement and select, view by table, hit submit to show data in database. |
|**Prometheus**|GOTO: http:localhost:9090/ and run ‘sensor\_value’ to show scraped data for that instance, change timestamp to show data scraped earlier. (Note: Prometheus does not support the historical display of data)|
## <a name="_heading=h.db1l1i8uj2v2"></a>**Data Wipe:**
Databases below will need manual cleanup of data, the others should automatically be cleared upon next startup of the Docker-Compose Stack.


|**Database:**|**Steps:**|
| :- | :- |
|**Timescale**|Run the clear\_database.sh located in the 303/timescale-testing/ folder.|
|**QuestDB**|via web console, run ‘drop table dpi;’       <http://localhost:9000/> |
##
## <a name="_heading=h.n1uxalle9tx0"></a>**
## **Script 1.1: Send a valid message**
### <a name="_heading=h.2et92p0"></a>***Script Description***
- <a name="_heading=h.tyjcwt"></a>Send a message from RabbitMQ to the logical time series queue.
- Confirm a message was stored in the database.
### ***Testing Requirements***
This test script covers the following specific testing requirements:

- <a name="_heading=h.3dy6vkm"></a>The output service should never fail to insert data from a valid message.
- The output service must never fail to receive a message. 
### ***Setup***
- Start the docker compose stack using “run.sh test”, and let all containers properly startup.
- Copy a valid message to RabbitMQ, for example:

*{*

`  `*"broker\_correlation\_id": "4798124-3094032",*

`  `*"p\_uid": 101,*

`  `*"l\_uid": 102,*

`  `*"timestamp": "2023-04-21T10:45:00Z",*

`  `*"timeseries": [*

`	`*{*

`  	`*"name": "Test Type",*

`  	`*"value": "Valid UAT"*

`	`*}*

`  `*]*

*}*
### <a name="_heading=h.1t3h5sf"></a>***Teardown***
- Stop the docker compose stack, and remove any trace of DB storage if necessary.
### ***Script Steps***

|**Step #**|**Test Action**|**Expected Results**|**Pass/ Fail**|
| :-: | :-: | :-: | :-: |
|1|Send a valid message to the queue using RabbitMQ Management.|Output service accepts the message, and saves the data points to the TSDB.|P|
|2|Retrieve data from the database.|All data within the message is returned.|P|
###
### ***Test Execution***

|**Date/Time**|**Tester**|**Test ID**|**Test Phase**|**Images**|**Status**|
| :- | :- | :- | :- | :- | :- |
|01/06/23 7:01 pm|Zak|Timescale1|System Cycle 1|<p>[Publish](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/TIMESCALE_UAT_1_1A.png?raw=true)</p><p>[Confirm](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/TIMESCALE_UAT_1_1B.png?raw=true)</p>|Passed|
|03/06/23 4:21 pm|Cal|QuestDB1|System Cycle 1|[Link](https://raw.githubusercontent.com/ZakhaevK/itc303-team3-broker/master/303/tests/UAT/QUSTDB_UAT_1_1.png)|Passed|
|04/06/23 5:03pm|Sara|InfluxDB1|System Cycle 1|<p>[Publish](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/INFLUXDB_UAT_1_1A.png)</p><p>[Confirm](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/INFLUXDB_UAT_1_1B.png)</p>|Passed|
|04/06/23 7:55pm|Rishabh|PromDB1|System Cycle 1|<p>[Step 1](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/PROMDB_UAT_1_1A.png)</p><p>[Step 2](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/PROMDB_UAT_1_1B.png)</p>|Passed|

#
## **Script 1.2: Send an invalid message**
### ***Script Description***
- Send an invalid message from RabbitMQ to the logical time series queue.
- Confirm a message was not stored in the database.
### ***Testing Requirements***
This test script covers the following specific testing requirements:

- The output service should not insert data from invalid messages.
- The output service must never fail to receive a message. 
### ***Setup***
- Start the docker compose stack using “run.sh”, and let all containers properly startup.
- Copy an valid message to RabbitMQ, for example: 

<a name="_heading=h.9okbtspo17ww"></a>*{*

<a name="_heading=h.jixpedjwr89n"></a>  *"borked\_correlation\_id": "420",*

<a name="_heading=h.1dxvu2acjkpk"></a>  *"p\_uid": 999,*

<a name="_heading=h.544p80n0peet"></a>  *"l\_uid": 999,*

<a name="_heading=h.e9cenjmrn01z"></a>  *"timestamp": "2023-04-21T10:45:00Z",*

<a name="_heading=h.i3mgqqlitmi8"></a>  *"timeseries": [*

<a name="_heading=h.md8ms4hdsl24"></a>    *{*

<a name="_heading=h.kfymyj472zyv"></a>      *"name": "Test Type",*

<a name="_heading=h.c7ea7nmwpano"></a>      *"value": "Invalid UAT"*

<a name="_heading=h.q2ylxi49f6gi"></a>    *}*

<a name="_heading=h.lubspsigawq6"></a>  *]*

<a name="_heading=h.puvx7u4qndal"></a>*}*
### ***Teardown***
- Stop the docker compose stack, and remove any other trace of DB storage if necessary.
### ***Script Steps***

|**Step #**|**Test Action**|**Expected Results**|**Pass/ Fail**|
| :-: | :-: | :-: | :-: |
|1|Send an invalid message to the queue using RabbitMQ Management.|Output service accepts message, but does not store the data points.|P|
|2|Retrieve data from the database.|No data is returned.|P|
###
### ***Test Execution***

|**Date/Time**|**Tester**|**Test ID**|**Test Phase**|**Images**|**Status**|
| :- | :- | :- | :- | :- | :- |
|01/06/23 6:58 pm|Zak|Timescale1|System Cycle 1|<p>[Publish](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/TIMESCALE_UAT_1_2A.png?raw=true)</p><p>[Confirm](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/TIMESCALE_UAT_1_2B.png?raw=true)</p>|Passed|
|03/06/23 4:45 pm|Cal|QuestDB1|System Cycle 1|[Link](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/QUESTDB_UAT_1_2.png?raw=true)|Passed|
|04/06/23 5:16 pm|Sara|InfluxDB1|System Cycle 2|<p>[Publish](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/INFLUXDB_UAT_1_2A.png)</p><p>[Confirm](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/INFLUXDB_UAT_1_2C.png)</p>|Passed|
|04/06/23 10:15pm|Rishabh|PromDB1|System Cycle 1|<p>[Step 1](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/PROMDB_UAT_1_2A.png)</p><p>[Step 2](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/PROMDB_UAT_1_2B.png)</p>|Passed|

#
## **Script 1.3: Send a valid message following an invalid message**
### ***Script Description***
- Send an invalid message from RabbitMQ to the logical time series queue.
- Confirm a message was not stored in the database.
- Send a valid message from RabbitMQ to the logical time series queue.
- Confirm a message was stored in the database.
### ***Testing Requirements***
This test script covers the following specific testing requirements:

- The output service should not insert data from invalid messages.
- The output service must never fail to receive a message. 
- The output service should never fail to insert data from a valid message.
### ***Setup***
- <a name="_heading=h.4d34og8"></a>Start the docker compose stack using “run.sh”, and let all containers properly startup.
- <a name="_heading=h.bba3qpqwi2jx"></a>Copy an Invalid Message to RabbitMQ, for example:

*{*

`  `*"borked\_correlation\_id": "420",*

`  `*"p\_uid": 999,*

`  `*"l\_uid": 999,*

`  `*"timestamp": "2023-04-21T10:45:00Z",*

`  `*"timeseries": [*

`    `*{*

`      `*"name": "Test Type",*

`      `*"value": "Invalid UAT"*

`    `*}*

`  `*]*

*}*

- <a name="_heading=h.od5y7zj5r3ij"></a>Copy a valid Message to RabbitMQ, for example:

{

`  `"broker\_correlation\_id": "4798124-3094032",

`  `"p\_uid": 101,

`  `"l\_uid": 102,

`  `"timestamp": "2023-04-21T10:45:00Z",

`  `"timeseries": [

`	`{

`  	`"name": "Test Type",

`  	`"value": "Valid UAT"

`	`}

`  `]

}
### ***Teardown***
- Stop the docker compose stack, and remove any trace of DB storage if necessary.
### ***Script Steps***

|**Step #**|**Test Action**|**Expected Results**|**Pass/ Fail**|
| :-: | :-: | :-: | :-: |
|1|Send an invalid message to the queue using RabbitMQ Management.|Output service accepts message, but does not store the data points.|P|
|2|Retrieve data from the database.|No data is returned.|P|
|3|Send a valid message to the queue using RabbitMQ Management.|Output service accepts message, and saves the data points to the TSDB.|P|
|4|Retrieve data from the database.|All data within the valid message is returned.|P|
### ***Test Execution***

|**Date/Time**|**Tester**|**Test ID**|**Test Phase**|**Images**|**Status**|
| :- | :- | :- | :- | :- | :- |
|01/06/23 6:55 pm|Zak|Timescale1|System Cycle 1|<p>[Invalid](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/TIMESCALE_UAT_1_3A.png?raw=true)</p><p>[Invalid](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/TIMESCALE_UAT_1_3B.png?raw=true)</p><p>[Valid](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/TIMESCALE_UAT_1_3C.png?raw=true)</p><p>[Valid](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/TIMESCALE_UAT_1_3D.png?raw=true)</p>|Passed|
|03/06/23 4:48 pm|Cal|QuestDB1|System Cycle 1|<p>[Invalid](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/QUESTDB_UAT_1_3A.png?raw=true)</p><p>[Valid](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/QUESTDB_UAT1_3B.png?raw=true)</p>|Passed|
|04/06/23 5:30 pm|Sara|InfluxDB1|System Cycle 1|<p>[Invalid](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/INFLUXDB_UAT_1_3a.png)</p><p>[Invalid](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/INFLUXDB_UAT_1_3C.png)</p><p>[Valid](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/INFLUXDB_UAT_1_3D.png)</p><p>[Valid](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/INFLUXDB_UAT_1_3F.png)</p>||
|04/06/23 10:30pm|Rishabh|PromDB1|System Cycle 1|<p>[Step 1](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/PROMDB_UAT_1_3A.png)</p><p>[Step 2](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/PROMDB_UAT_1_3B.png)</p><p>[Step 3](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/PROMDB_UAT_1_3C.png)</p><p>[Step 4](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/tests/UAT/PROMDB_UAT_1_3D.png)</p>|Passed|

Page**  of  | 5/24/2023 | **Team 3**
