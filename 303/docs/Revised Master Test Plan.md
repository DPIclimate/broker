

|**DPI – IoTa Time-series Database**| |
| :- | :- |
|TSDB Master Test Plan|`  `Date:  31.03.23|




**IoTa Time-series Database**
**Master Test Plan**

**Executive summary**

**Project objective**
  - The  goal of this project can be summarised with the following points:
  - Implement a new TSDB for storing data received from internal messages within IoTa application, currently RabbitMQ is the message broker
  - Implement a service which will take the data and store it within the new TSDB.
  - Implement API features to allow for pulling of data from the TSDB.
  - Create scripts that allow for backup management
  - Implement the ability to convert and push existing IoTa DB data to IoTa internal message format and into TSDB
  - Meet the performance and design standards expected by DPI.

**Test approach**
 - Unit testing will be used to confirm the functional requirements are implemented as expected and error cases are handled correctly. This could involve just an example message in the format to be used, to allow the program to parse it. Could also include the other database formats as well.
 - Integration Testing should focus on interaction with specific functionality between Docker containers, this will include from API to service, service to TSDB, web interface to API.
 - System Testing will monitor the full use cases and the data that flows between different elements of the project. This includes message parsing, and extraction of data points, and finally the storage within the TSDB. Also includes the retrieval of data from the TSDB via an API request to the service from the web interface.
 - Acceptance Testing will be similar to System testing, but will be focused on getting feedback from the stakeholders to confirm that the functionality is as they expected, or if there are changes/additions that could be made to better fit their needs.

**Test objectives**
  - Confirm functionality of individual methods are correct.
  - Verify interaction between Docker containers is as expected.
  - Catch errors in data storage and retrieval and ensure correct handling.
  - Confirm scripts perform the desired tasks, and offer all necessary options.
  - Test various TSDB to make a decision on what fits best for this project.

Table of Contents

[1](#_heading=h.gjdgxs)[	](#_heading=h.gjdgxs)Introduction	4

[1.1](#_heading=h.30j0zll)[	](#_heading=h.30j0zll)Project and project objective	4

[1.2](#_heading=h.1fob9te)[	](#_heading=h.1fob9te)Objective of the master test plan	4

[2](#_heading=h.3znysh7)[	](#_heading=h.3znysh7)Documentation	5

[2.1](#_heading=h.2et92p0)[	](#_heading=h.2et92p0)Basis for the master test plan	5

[2.2](#_heading=h.tyjcwt)[	](#_heading=h.tyjcwt)Test basis	5

[3](#_heading=h.3dy6vkm)[	](#_heading=h.3dy6vkm)Test strategy	6

[3.1](#_heading=h.1t3h5sf)[	](#_heading=h.1t3h5sf)Risk analyses	6

[3.1.1](#_heading=h.4d34og8)[	](#_heading=h.4d34og8)Product Risk Analysis	6

[3.1.2](#_heading=h.2s8eyo1)[	](#_heading=h.2s8eyo1)Technical Risk Analysis	7

[3.2](#_heading=h.3rdcrjn)[	](#_heading=h.3rdcrjn)Test strategy	8

[4](#_heading=h.lnxbz9)[	](#_heading=h.lnxbz9)Test Levels	9

[4.1](#_heading=h.44sinio)[	](#_heading=h.44sinio)The <name test level>	9

[4.1.1](#_heading=h.z337ya)[	](#_heading=h.z337ya)Entrance and Exit Criteria	9

[4.1.2](#_heading=h.3j2qqm3)[	](#_heading=h.3j2qqm3)Test Environment	9

[4.1.3](#_heading=h.1y810tw)[	](#_heading=h.1y810tw)Test Objectives	9




1. # <a name="_heading=h.gjdgxs"></a>Introduction
   1. ## <a name="_heading=h.30j0zll"></a>Project and project objective
The goal of the project is to identify the best Time-series Database (TSDB) with consideration for DPI’s requirements, and implement it into the existing IoTa Docker compose structure. Then we will develop the service that will handle parsing of messages from the RabbitMQ implementation into the format used by the TSDB and subsequently storing the data points. 

This same service will also require an API for interaction that will be usable to retrieve data from the TSDB, which will have the service modify the TSDB message back into IoTa message format to be read by the web interface currently utilised by IoTa.

Another functional requirement of the system is to be able to convert data from the existing IoTa database into IoTa internal message format and add it to the TSDB.

Backup and restore scripts are also a requirement of the TSDB implementation.

Development of these features will be done within DPI’s constraints, in which the developed service will need to handle a message roughly every 5 seconds, and store it for use later. The requirements state that we must develop the service in Python, as DPI has provided us with a Docker image for this purpose. For the TSDB, we must ensure that it does not require a cloud implementation, and can be hosted within a Docker container.
1. ## <a name="_heading=h.1fob9te"></a>Objective of the master test plan
The objective of the Master Test Plan (MTP) is to inform all who are involved in the test process about the approach, the activities - including the mutual relations and dependencies, and the final products to be delivered.

The master test plan describes the test approach, the activities and (end) products.

Specifically for this project, the objective will be to provide criteria for testing against the TSDB implementation, in which once unit testing is done with the service, we can develop tests to properly benchmark the performance of the service. Each TSDB candidate will be tested and we can make a decision on what would fit best with the dataset, and integrate well with our service.
1. # <a name="_heading=h.3znysh7"></a>Documentation
This chapter describes the documentation used in relation with the master test plan. The described documentation concerns a first inventory and will be elaborated, actualized and detailed at a later stage, during the separate test levels.
1. ## <a name="_heading=h.2et92p0"></a>Basis for the master test plan
The following documents are used as the basis for this master test plan.

|**Document name**|**Date**|**Author**|
| :- | :- | :- |
|Project\_Vision.md|4\.6.23|TEAM 3|
|Revised Risk-List.xslx|4\.6.23|TEAM 3|
1. ## <a name="_heading=h.tyjcwt"></a>Test basis
The test basis contains the documentation that serves as the basis for the tests that have to be executed. The overview below describes the documentation that is the starting point for testing. 

|**Document name**|**Date**|**Author**|
| :- | :- | :- |
|revised\_supporting\_requirements.md|1\.6.23|TEAM 3|
|Final\_Architecture\_Notebook.md|4\.6.23|TEAM 3|


1. # <a name="_heading=h.3dy6vkm"></a>Test strategy
Testing will cover the core and most likely risks to ensure both expected outcomes and correct error handling to assure the stakeholders of a correct and thoughtful implementation of the project.

For this project, the critical points can be determined by looking at how often the code executes, how varied the input and output data is expected to be and if an error occurs, how many other processes will the error affect.

The first step in determining the test strategy is the execution of a product risk analysis. This is elaborated in §3.1.

The test strategy is subsequently based on the results of the risk analysis. The test strategy lays down what, how and when (in which test level) is being tested and is focused on finding the most important defects as early as possible for the lowest costs. This can be summarised as testing with an optimal use of the available capacity and time. The test strategy is described in §3.3.
1. ## <a name="_heading=h.1t3h5sf"></a>Risk analysis
   1. ### <a name="_heading=h.4d34og8"></a>Product Risk Analysis
The product risks are determined in cooperation with the client and the other parties involved. Product risks are those risks associated with the final product failing to meet functional requirements and required system quality characteristics (NFRs) This product risk analysis (PRA) is comprised of two steps:

|**Product Risk**|**Characteristic**|**Description**|**Risk Class**|
| :- | :- | :- | :- |
|1|Performance|<p>TSDB design choices fail to meet performance standards set within the Docker compose environment.</p><p>Lowly rated as our performance requirements are low and all of the possible TSDB are capable of meeting the needs even with a poor implementation.</p>|C|
|2|Compatibility|TSDB suffers from integration issues within the Docker compose stack|A|
|3|Integrity|<p>Service fails to extract all the desired details from the data, resulting in the loss of quality data.</p><p>Message parsing can be difficult to get correct, especially with varying message contents and changing identifiers for the data.</p>|A|
|4|Compatibility|API additions fail to be implemented correctly within the IoTa interface.|C|
|5|Compression|The nature of IoT sensors means a steady supply of data, which in turn results in large data sizes. Good compression can be seen as a critical component of ensuring long term success of the project.|B|

The extent of the risk (the risk class) is dependent on the chance of failure (how big the chance is that it goes wrong?) and it depends on the damage for the organisation if it actually occurs.

1. ### <a name="_heading=h.2s8eyo1"></a>Technical Risk Analysis
Technical risks are determined in cooperation with the analyst/designers and programmers involved. Technical risks are development risks associated with failing to create a system that behaves according to specifications derived from requirements. (I.E. those aspects of development that pose particular challenges.) This technical risk analyses (TRA) is comprised of two steps:

|**Technical risk**|**Risk Area**|**Description**|**Risk Class**|
| :- | :- | :- | :- |
|1|Parsing|Messages are parsed incorrectly such that data is changed beyond expectation, messages that should be rejected are not, messages fail to process into TSDB|A|
|2|Connectivity|Connection to related IoTa containers is inconsistent, resulting in lost data or functionality.|C|
|3|Interfacing|API requests fail to call the correct methods within the service.|B|
|4|Interfacing|CLI scripts fail to execute correctly. These can be hard to debug and perform correct testing on.|C|
|5|TSDB Schema|Schema is used loosely here; If data is not stored correctly in TSDB then the retrieved data may not hold any value rendering TSDB implementation worthless.|A|

<a name="_heading=h.17dp8vu"></a>
1. ## <a name="_heading=h.3rdcrjn"></a>Test strategy
<a name="_heading=h.26in1rg"></a>For each risk from the product and technical risk analysis, the risk class determines the thoroughness of the test. Risk class A is the highest risk class and C the lowest. The test strategy is subsequently focused on covering the risks with the highest risk class as early as possible in the test project.

<table><tr><th rowspan="2">Risk</th><th rowspan="2">Description</th><th rowspan="2">Risk Cat</th><th colspan="6">Test Level</th></tr>
<tr><td>SR</td><td>Unit</td><td>Int</td><td>ST</td><td>FAT</td><td>UAT</td></tr>
<tr><td>Performance</td><td>TSDB design choices fail to meet performance standards set within the Docker compose environment.</td><td>C</td><td>***</td><td></td><td>*</td><td>**</td><td>**</td><td>**</td></tr>
<tr><td>Compatibility</td><td valign="top">TSDB suffers from integration issues within the Docker compose structure</td><td>A</td><td>***</td><td></td><td>***</td><td>**</td><td></td><td></td></tr>
<tr><td>Integrity</td><td>Service fails to extract all the desired details from the data, resulting in loss of quality data.</td><td>C</td><td>**</td><td>**</td><td>***</td><td>**</td><td></td><td></td></tr>
<tr><td>Compatibility</td><td>API additions fail to be implemented correctly within the IoTa interface.</td><td>C</td><td>**</td><td></td><td>**</td><td>*</td><td>**</td><td>**</td></tr>
<tr><td>Parsing</td><td>Messages are parsed incorrectly.</td><td>A</td><td>**</td><td>                                   </td><td></td><td></td><td>*</td><td></td></tr>
<tr><td>Connectivity</td><td>Connection to related IoTa containers is inconsistent, resulting in lost data or functionality.</td><td>C</td><td>**</td><td></td><td>***</td><td></td><td>**</td><td>*</td></tr>
<tr><td>Interfacing</td><td>API requests fail to call the correct methods within the service.</td><td>C</td><td>*</td><td>*</td><td>***</td><td></td><td></td><td></td></tr>
<tr><td valign="top">Interfacing</td><td>CLI scripts fail to execute correctly.</td><td>C</td><td></td><td>*</td><td></td><td>***</td><td>**</td><td>*</td></tr>
<tr><td valign="top">Compression</td><td>TSDB data is compressed</td><td>B</td><td>***</td><td></td><td></td><td></td><td>**</td><td></td></tr>
<tr><td valign="top">TSDB Schema</td><td>Data inserted into TSDB correctly so that output is as expected</td><td>A</td><td></td><td></td><td></td><td>*</td><td>***</td><td>*</td></tr>
</table>



Legend for the table above:

|RC|Risk class (from product and technical risk analysis, where A=high risk, B=average risk, C=low risk)|
| :- | :- |
|SR|Static Review of the various intermediary products (requirements, functional design, technical design). Checking and examining artefacts without executing the software|
|Unit|Unit test and Unit integration test|
|Integration|Integration tests (low level (L), high level(H))|
|FAT|Functional acceptance test (alpha stage UAT)|
|UAT|User acceptance test (Beta stage UAT)|
|ST|System test (functional scenario testing (F), system quality scenario testing (S))|
|⬤|Limited thoroughness of the test|
|⬤⬤|Medium thoroughness of the test|
|⬤⬤⬤|High thoroughness of the test|
|<blank>|If a cell is blank, it means that the relevant test or evaluation level does not have to be concerned with the characteristic|

## <a name="_heading=h.u7gh71q1vqs"></a>
1. ## <a name="_heading=h.wialh1yn8iy"></a>TSDB Selection
When we assess the potential time series database implementations, we will need to compare them fairly against each other in order to decide a best pick for this project.

<a name="_heading=h.xhtx2nr6qstu"></a>**Constraints:**

- <a name="_heading=h.987pj52nnlfn"></a>All test data will be taken from the backup database (~11GB total) to ensure it is as close to realistic as possible.
- <a name="_heading=h.9zp6j0g0zuzs"></a>Where possible, tests are performed on test development systems, each database is to be partially implemented to perform the required tests.
- <a name="_heading=h.wzaka4190vr"></a>For the more subjective aspects such as documentation, it will be judged by team consensus.
- <a name="_heading=h.f5dy9jrnj4dr"></a>All TSDB we are looking into have similar licences and are open source, free and self hosted.
- <a name="_heading=h.m7h79lxa0r6f"></a>Weighting of the tests and results will be based on architecture requirements, vision, and other supporting documentation. It should be transferred into the table, however space requirements in this document would not allow that.

<a name="_heading=h.xxq29xb9r8o0"></a>We will base selection off the following table (layout subject to change)::

||**QUESTDB**|**INFLUXDB**|**PROMETHEUS**|**TIMESCALE**|
| :- | :-: | :-: | :-: | :-: |
|**Single Insert Performance**|||||
|**Bulk Insert Performance**|||||
|**Query Performance**|||||
|**Compression**|||||
|**Scalability**|||||
|**Compatibility**|||||
|*MISC*|||||
|**Visualisation**|||||
|**Ease of Use**|||||
|**Documentation**|||||

<a name="_heading=h.5qm0529hs8vd"></a>Where, 

- **Single Insert Performance:** the time measured to perform a single insert into a database.
- **Bulk Insert Performance:** the time taken to ingest an entire backup database.
- **Query Performance:** the time taken to complete a range of queries, both for single records, and bulk records.
- **Compression**: The footprint size of the TSDB once all data is ingested -- as not all databases have inbuilt compression, it can be a custom implementation for compression.
- **Scalability:** If we double or triple the test data, how much degradation appears on the previous tests?
- **Compatibility**: How well the implementation fits with IoTa architecture, is there room to expand its functionality for other tasks? 
- **Visualisation**: Does the TSDB include visualisation, or is it trivial to link it with some visualisation? Is this easy to use, intuitive?
- **Ease of Use:** Is the database trivial to implement, is it easy to work on, or is it difficult and adding features or fixes is time consuming?
- **Documentation**: Does the documentation resolve questions and issues? Is it easy to navigate and provide good insight to the database?
1. # <a name="_heading=h.lnxbz9"></a>Test Levels
<a name="_heading=h.35nkun2"></a>For this MTP the following test levels are acknowledged:

|**Test level**|**Goal**|
| :- | :- |
|Unit testing:|The aim is to test each part of the software separately and to confirm that individually they function as expected. |
|Integration testing:|In this testing phase, different software modules are combined and tested as a group to make sure that the integrated system is ready for system testing. Integration testing checks the data flow from one module to other modules.|
|System testing:|System testing is performed on a complete, integrated system. It allows checking the system's compliance as per the requirements. It tests the overall interaction of components. It involves load, performance, reliability and security testing.|
|Acceptance testing:|Acceptance testing is a test conducted to find if the requirements of a specification or contract are met as per its delivery.|

1. ## <a name="_heading=h.1ksv4uv"></a><a name="_heading=h.44sinio"></a>The Unit Testing Level 
<a name="_heading=h.2jxsxqh"></a> The primary goal of unit testing is to ensure that each individual piece of the implementation features acts as expected. This includes correct message parsing from within the IoTa Decoder process, back up scripts actually back up the data, restore scripts correctly restore from the back up, the time series database stores the data correctly and so on.
1. ### <a name="_heading=h.z337ya"></a>Entrance and Exit Criteria
Entry Criteria:

- Processes have at least been partially implemented into IoTa stack
- Methods, Functions, Scripts, or Classes are considered complete and their functionality can be tested regardless if it has been added to IoTa stack

Exit Criteria:

- The execution of all tests pass.
- Test coverage contains all critical components such as message parsing, retrieval, backup and restore.
- All known defects have been resolved.

1. ### <a name="_heading=h.3j2qqm3"></a>Test Environment
<a name="_heading=h.pmmkg3rr1d6k"></a>For the processes such as TSDB Decoder, we can use the test deployment without issue to a range of inputs and ensure we get the desired output from the process.

<a name="_heading=h.9v78g8opjb3y"></a>It is important to note that there is little difference between the production deployment and the test deployment, where persistent storage is the only difference.

<a name="_heading=h.6c5gxeo49z3g"></a>The majority of scripts will still require the test environment up and running as they may require access to DB or TSDB.
1. ### Test Objectives

|**Risk**|**Test Goals** |**Risk Verification**|**Schedule**|
| :- | :- | :- | :- |
|Integrity: Service fails to extract all the desired details from the data, resulting in the loss of quality data.|Confirm for each message type, that the data is correct as per the messages.|Check the resulting data for each message format is not lacking in details/data points.|During implementation of the functions related to handling messages.|
|Parsing: A required message format is not properly recognized by the service.|Ensure the desired message formats are handled correctly and are not rejected or extracted with invalid data.|Test each message type with examples either provided by DPI or created based on our understanding.|During implementation of the functions related to handling messages.|
|Parsing: data formats are modified such that errors may occur.|Ensure that input data and the output data are of the correct data types.|Confirm that the data type is consistent among all data for desired types.|During implementation of the functions related to handling messages.|
|Interfacing: API requests fail to call the correct methods within the service.|Ensure the API is calling the correct functions when it receives a request.|Test each function of the API, and the different amounts of requested data to confirm the correct details are included in the function calls.|During implementation of the API, follows later than prior unit-testing.|
|API: ensure queries to TSDB return the correct data|Output from TSDB queries are expected depending on the input.|Confirm that given a set of varied inputs and TSDB data, the output data from TSDB/API is as expected|During API implementation|

1. ## The Integration testing Level 
The primary goal of integration testing is to confirm the service interacts correctly with individual components of IoTa, and also the new TSDB.
1. ### Entrance and Exit Criteria
Entry criteria is to have the other components of the Docker compose stack running, and ready to receive/send requests to the service.

Exit criteria is each individual component can properly interact with the service in isolation between two of the components.
1. ### Test Environment
Testing of functions will begin after the service has connected to the related component to be tested. For example the API and the service will be tested to confirm the requests reach the service and work as expected.

The TSDB will be tested in conjunction with the message parsing functionality.
1. ### Test Objectives

|**Risk**|**Test Goals** |**Risk Verification**|**Schedule**|
| :- | :- | :- | :- |
|Performance: TSDB design choices fail to meet performance standards set within the Docker compose environment.|Ensure the service can handle multiple messages and save them to the TSDB.|Setup the service with multiple messages to be saved to the TSDB. Check that all messages were saved to the TSDB and no data is missing.|During TSDB testing, as it will aid in decision making.|
|Compatibility: TSDB suffers from integration issues within the Docker compose structure|Ensure TSDB works within the Docker compose environment. Help identify the best TSDB to be used.|Setup the TSDB within the Docker compose stack, and have it interact with the service via a service request.|During TSDB testing.|
|Integrity: Service fails to extract all the desired details from the data, resulting in loss of quality data.|Ensure the desired details are retrieved from messages sent to the API and also IoTa DB CLI prompts.|Check that correct data points are extracted from the data of each message type. |Can be tested alongside other RabbitMQ related message handling tests, and also after for CLI requests.|
|Compatibility: API additions fail to be implemented correctly within the IoTa interface.|Ensure the web interface is providing the API with sufficient detail for different methods.|Check the output functions of the API based on what is done within the web interface. |Late stage testing, as it involves the IoTa interface and not key functionality.|
|Connectivity: Connection to related IoTa containers is inconsistent, resulting in lost data or functionality.|Ensure there is no issue in the service that may result in dropped connections between container elements.|Perform an extended run for both streams of messages from the API, and also separately to the TSDB.|Can be tested alongside other RabbitMQ related message handling tests.|
|Interfacing: API requests fail to call the correct methods within the service.|Test communication from the API to the service, to ensure that all method calls perform the right tasks and result in proper results.|Check data resulting from the method calls of the API, and see if the output is accurate to the data.|Can be tested alongside other RabbitMQ related message handling tests.|

1. ## The System Testing Level 
The primary goal of system testing is to confirm the service interacts correctly with all elements of IoTa working together. This is essentially full use cases run with the full architecture in place.
1. ### Entrance and Exit Criteria
Entry criteria is to have the full set of Docker containers running, and ready to receive/send requests to the service.

Exit criteria is each full use case results in the correct data being stored and displayed, as well as scripts performing the correct tasks on multiple systems.
1. ### Test Environment
Testing of the service and TSDB in conjunction with the Docker containers will be done by starting at the beginning of each use case, and following the full process to test each method within a close to live environment.

The TSDB will likely be monitored further for performance issues, and if there’s any issues with our design choices, or its capabilities within this implementation.
1. ### Test Objectives

|**Risk**|**Test Goals** |**Risk Verification**|**Schedule**|
| :- | :- | :- | :- |
|Performance: TSDB design choices fail to meet performance standards set within the Docker compose environment.|Check the performance of the TSDB schema, and if both retrieving and storing data is efficient.|Check response times for each use case involving the TSDB. Determine if this is a result of the TSDB itself, or if another part of the system architecture is responsible.|Monitor during each run of a method within the full system, while other tasks are being performed.|
|Compatibility: TSDB suffers from integration issues within the Docker compose structure|Identify if there is any issue in the TSDB compatibility within the full Docker compose structure.|Check if data is lacking any required details, or if the TSDB is simply not working as intended during specific operations.|Monitor during each portion of a method test that interacts with the TSDB.|
|Integrity: Service fails to extract all the desired details from the data, resulting in loss of quality data.|Check the output of the service within the TSDB within the full test environment.|Following message processing, check for invalid data within the TSDB, may also be worth checking output within the web interface after retrieval of data.|First part of the system test, a follow-up to population of the database using RabbitMQ messages sent to the service.|
|Compatibility: API fails to be implemented correctly within the IoTa interface.|Confirmation of the API functionality during the live environment.|Check the output of queries from the user interface to the API, and confirm data, and ranges of data is accurate to the request.|Second part of the test, relies on the database storing the correct data.|
|Interfacing: CLI scripts fail to execute correctly.|Check functionality and reliability of scripts during the service running.|Confirm function of IoTa database table import into TSDB. Confirm backup scripts perform relevant functions, and work without issue.|Can be done at any point after beginning of System testing. Backup restore should likely be done after testing of the live environment, unless it is intended to work that way and import lost data later.|

1. ## The Acceptance Testing Level 
The primary goal of acceptance testing is to confirm the service meets the specific requirements set by DPI through testing with the purpose of receiving their feedback.
1. ### Entrance and Exit Criteria
Entry criteria is the system testing is successful, and is ready to be presented to the stakeholders to determine if there is any issue, or missing functionality.

Exit criteria is confirmation by DPI that the service, TSDB, and API implementation meets the requirements that they have set, and the work is of a high standard.
1. ### Test Environment
Either presenting the test to stakeholders via a stream, or providing them with our repo to test on their own system, and we can advise on how to interact with the system either live or using a guide.
1. ### Test Objectives

|**Risk**|**Test Goals** |**Risk Verification**|**Schedule**|
| :- | :- | :- | :- |
|Performance: TSDB design choices fail to meet performance standards set within the Docker compose environment.|To verify if that design is acceptable by the stakeholder’s standards, or clash with an existing part of the architecture.|Check with stakeholders if there is any concern regarding a specific design element, or performance metric that is related to the TSDB.|Following some demoing of the use cases.|
|Compatibility: API additions fail to be implemented correctly within the IoTa interface.|To verify by the stakeholders standards that no issue is occurring between the API and expected functionality.|Have the stakeholders try multiple inputs that would be often used during production, and check results.|Following the database being populated with messages.|
|Connectivity: Connection to related IoTa containers is inconsistent, resulting in lost data or functionality.|To verify connection between the service and related elements experiences no issues with DPI’s setup.|Verify all data flows remain uninterrupted, and nothing is lost during stakeholder test.|Throughout acceptance testing to verify actions as they’re performed.|
|Interfacing: CLI scripts fail to execute correctly.|Confirm functionality of each script is sufficient for the needs of DPI.|Have the stakeholders run through the scripts and confirm options are sufficient, and results are as expected.|Performed at the end of the acceptance test.|



## <a name="_heading=h.outpwmcji25b"></a>5.1	Change Log
13/05/23 - Removed Version history in favour of adding change log at end of document, for recording changes after initial publishing of document for LCOM. Sara M.
Minor spelling and grammar fixes, updating tense of document. Sara M.

23/05/23 - Refined Executive Summary project objectives. Callum B.
Reworded initial paragraph in Executive Summary - Test Approach for added clarity. Callum B.
Minor grammar fixes in Executive Summary - Test Objectives. Callum B.
Added paragraph after second paragraph in 1.1 Project and Project Objective for clarity. Callum B.
First two paragraphs of 3 Test Strategy condensed and reworked. Callum B.
Additional risk added to 3.1.1 Product Risk Analysis, as well as expanding description of existing risks. Risk Classes updated. Callum B.
Additional risk added to 3.1.2 Technical Risk Analysis, as well as expanding description of existing risks. Risk classes updated. Callum B. 
Risks from above edits added to 3.2 Test Strategy table. Above edited risk classes updated here to match. Description updated for Parsing. Callum B.

24/05/23 - Reworked 4.1 The Unit Testing Level, to enhance clarity surrounding unit test requirements. Sara M.
Expanded upon primary goal, 4.1.1 Entrance and Exit Criteria, 4.1.2 Test Environment, and 4.1.3 Test Objectives. Callum B.
Syntax change in 4 Test Levels table for Goal or Unit Testing. Callum B.

4/5/23 - added 3.3 - TSDB selection, testing guide.
