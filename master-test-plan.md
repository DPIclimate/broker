**IoTa Time-series Database**  
**Master Test Plan**

Version Information

<table>
<colgroup>
<col style="width: 9%" />
<col style="width: 20%" />
<col style="width: 47%" />
<col style="width: 21%" />
</colgroup>
<thead>
<tr class="header">
<th><strong>Version</strong></th>
<th><strong>Date</strong></th>
<th><strong>Remarks</strong></th>
<th><strong>Author</strong></th>
</tr>
</thead>
<tbody>
<tr class="odd">
<td>0.1</td>
<td>31/03/23</td>
<td>Added to the Introduction, and documents section of the Master Test
Plan. These are near completion.</td>
<td>Zak K</td>
</tr>
<tr class="even">
<td>0.2</td>
<td>02/04/23</td>
<td><p>First draft of the Test Strategy written.</p>
<p>Executive summary began to be written.</p></td>
<td>Zak K</td>
</tr>
<tr class="odd">
<td>0.3</td>
<td>03/04/23</td>
<td><p>First draft of Test Plan written.</p>
<p>Lacking acceptance testing section at this time.</p></td>
<td>Zak K</td>
</tr>
<tr class="even">
<td>0.5</td>
<td>04/04/23</td>
<td><p>Full draft document completed.</p>
<p>Risks may be added/changed, and tests expanded as the project
matures.</p></td>
<td>Zak K</td>
</tr>
<tr class="odd">
<td>0.6</td>
<td>07/04/23</td>
<td>Removed blue template text.</td>
<td>Zak K</td>
</tr>
<tr class="even">
<td>0.9</td>
<td>09/04/23</td>
<td>Made small adjusts and additions to Test objectives/levels</td>
<td>Zak K</td>
</tr>
</tbody>
</table>

# Executive summary

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>


<td><p><strong>Project objective</strong></p>
<p>The goal of this project can be summarised with the following
points:</p>
<ul>
<li><p>Implement a new TSDB for storing data received from the existing
RabbitMQ container.</p></li>
<li><p>Implement a service which will take the data and store it within
the new TSDB.</p></li>
<li><p>Implement API features to allow for pulling of data from the
TSDB.</p></li>
<li><p>Create scripts that allow for backup management, and also
importing of data from the existing IoTa database tables.</p></li>
<li><p>Meet the performance and design standards expected by
DPI.</p></li>
</ul></th>
</tr>
<tbody>

<td><p><strong>Test approach</strong></p>
<p>Unit testing will primarily be necessary to make sure the service can
extract the desired data points from the messages provided by RabbitMQ.
This could involve just an example message in the format to be used, to
allow the program to parse it. Could also include the other database
formats as well.</p>
<p>Integration Testing should focus on interaction with specific
functionality between Docker containers, this will include from API to
service, service to TSDB, web interface to API.</p>
<p>System Testing will monitor the full use cases and the data that
flows between different elements of the project. This includes message
parsing, and extraction of data points, and finally the storage within
the TSDB. Also includes the retrieval of data from the TSDB via an API
request to the service from the web interface.</p>
<p>Acceptance Testing will be similar to System testing, but will be
focused on getting feedback from the stakeholders to confirm that the
functionality is as they expected, or if there are changes/additions
that could be made to better fit their needs.</p></td>
</tr>
<tr class="even">
<td><p><strong>Test objectives</strong></p>
<ul>
<li><p>Confirm functionality of individual methods is correct.</p></li>
<li><p>Verify interaction between Docker containers is as
expected.</p></li>
<li><p>Minimise errors in data storage and retrieval.</p></li>
<li><p>Confirm scripts perform the desired tasks, and offer all
necessary options.</p></li>
<li><p>Test various TSDB to make a decision on what fits best for this
project.</p></li>
</ul></td>
</tr>
</tbody>
</table>

# Table of Contents

[1 Introduction [4](#introduction)]

[1.1 Project and project objective
[4](#project-and-project-objective)]

[1.2 Objective of the master test plan
[4](#objective-of-the-master-test-plan)]

[2 Documentation [5](#documentation)]

[2.1 Basis for the master test plan [5](#basis-for-the-master-test-plan)]

[2.2 Test basis [5](#test-basis)]

[3 Test strategy [6](#test-strategy)]

[3.1 Risk analyses [6](#risk-analyses)]

[3.1.1 Product Risk Analysis
[6](#product-risk-analysis)]

[3.1.2 Technical Risk Analysis
[7](#technical-risk-analysis)]

[3.2 Test strategy [8](#test-strategy-1)]

[4 Test Levels [9](#test-levels)]

[4.1 The \<name test level\> [9](#_Toc37168495)]

[4.1.1 Entrance and Exit Criteria
[9](#entrance-and-exit-criteria)]

[4.1.2 Test Environment [9](#test-environment)]

[4.1.3 Test Objectives [9](#_Toc37168498)]

# Introduction

## Project and project objective

The goal of the project is to identify the best Time-series Database
(TSDB) with consideration for DPI’s requirements, and implement it into
the existing IoTa Docker compose structure. Then we will develop the
service that will handle parsing of messages from the RabbitMQ
implementation into the format used by the TSDB and subsequently storing
the data points.

This same service will also require an API for interaction that will be
usable to retrieve data from the TSDB, which will have the service
modify the TSDB message back into IoTa message format to be read by the
web interface currently utilised by IoTa.

There will also need to be extra scripts that can be run via CLI, which
will be capable of converting current IoTa database message tables into
the format used by the TSDB for storage.

Though not explicitly stated to be CLI based, this may also include
backing up the TSDB data, and restoring to a previous backup.

Development of these features will be done within DPI’s constraints, in
which the developed service will need to handle a message roughly every
5 seconds, and store it for use later. The requirements state that we
must develop the service in Python, as DPI will provide us with a Docker
image at a later date for this purpose. For the TSDB, we must ensure
that it does not require a cloud implementation, and can be hosted
within a Docker image.

## Objective of the master test plan

The objective of the Master Test Plan (MTP) is to inform all who are
involved in the test process about the approach, the activities,
including the mutual relations and dependencies, and the (end) products
to be delivered.

The master test plan describes the test approach, the activities and
(end) products.

Specifically for this project, the objective will be to provide criteria
for testing against the TSDB implementation, in which once unit testing
is done with the service, we can develop tests to properly benchmark the
performance of the service. Each TSDB candidate will be tested and we
can make a decision on what would fit best with the dataset, and
integrate well with our service.

# Documentation

This chapter describes the documentation used in relation with the
master test plan. The described documentation concerns a first inventory
and will be elaborated, actualized and detailed at a later stage, during
the separate test levels.

## Basis for the master test plan

The following documents are used as basis for this master test plan.

| **Document name**      | **Version** | **Date** | **Author** |
|------------------------|-------------|----------|------------|
| inception_vision.md    | 1.0         | 27.03.23 | Sara       |
| Inception_risk_list.md | 1.0         | 29.03.23 | Callum     |

## Test basis

The test basis contains the documentation that serves as basis for the
tests that have to be executed. The overview below describes the
documentation that is the starting point for testing.

| **Document name**                    | **Version** | **Date** | **Author** |
|--------------------------------------|-------------|----------|------------|
| inception_supporting_requirements.md | 1.0         | 27.03.23 | Zak        |
| Architecture_notebook.md             | 1.0         | 29.03.23 | Rishabh    |

Further documentation will likely appear here as full use cases and more
specific project focused documents are developed. More information is
currently set to be provided to us in the next few days.

# Test strategy

The time available for testing is limited; not everything can be tested
with equal thoroughness. This means that choices have to be made
regarding the depth of testing. Also, it is strived to divide test
capacity as effective and efficient as possible over the total test
project. This principle is the basis of the test strategy.

The test strategy is based on risks: a system has to function in
practice to an extent that no unacceptable risks for the organization
arise from it. If the delivery of a system brings along many risks,
thorough testing needs to be put in place; the opposite of the spectrum
is also true: 'no risk, no test'.

The first step in determining the test strategy is the execution of a
product risk analyses. This is elaborated in §3.1.

The test strategy is subsequently based on the results of the risk
analyses. The test strategy lays down what, how and when (in which test
level) is being tested and is focused in finding the most important
defects as early as possible for the lowest costs. This can be
summarized as testing with an optimal use of the available capacity and
time. The test strategy is described in §3.3.

## Risk analyses

### Product Risk Analysis

The product risks are determined in cooperation with the client and the
other parties involved. Product risks are those risks associated with
the final product failing to meet functional requirements and required
system quality characteristics (NFRs) This product risk analyses (PRA)
is comprised of two steps:

| **Product Risk** | **Characteristic** | **Description**                                                                                        | **Risk Class** |
|------------------|--------------------|--------------------------------------------------------------------------------------------------------|----------------|
| 1                | Performance        | TSDB design choices fail to meet performance standards set within the Docker compose environment.      | B              |
| 2                | Compatibility      | TSDB suffers from integration issues within the Docker compose structure                               | A              |
| 3                | Integrity          | Service fails to extract all the desired details from the data, resulting in the loss of quality data. | C              |
| 4                | Compatibility      | API additions fail to be implemented correctly within the IoTa interface.                              | C              |

The extent of the risk (the risk class) is dependent on the chance of
failure (how big the chance is that it goes wrong?) and it depends on
the damage for the organization if it actually occurs.

### Technical Risk Analysis

Technical risks are determined in cooperation with the analyst/designers
and programmers involved. Technical risks are development risks
associated with failing to create a system that behaves according to
specifications derived from requirements. (I.E. those aspects of
development that pose particular challenges.) This technical risk
analyses (TRA) is comprised of two steps:

| **Technical risk** | **Risk Area** | **Description**                                                                                 | **Risk Class** |
|--------------------|---------------|-------------------------------------------------------------------------------------------------|----------------|
| 1                  | Parsing       | A required message format is not properly recognized by the service.                            | B              |
| 2                  | Connectivity  | Connection to related IoTa containers is inconsistent, resulting in lost data or functionality. | C              |
| 3                  | Interfacing   | API requests fail to call the correct methods within the service.                               | B              |
| 4                  | Interfacing   | CLI scripts fail to execute correctly.                                                          | C              |

## Test strategy

For each risk from the product and technical risk analysis the risk
class determines the thoroughness of the test. Risk class A is the
highest risk class and C the lowest. The test strategy is subsequently
focused on covering the risks with the highest risk class as early as
possible in the test project.

| Risk          | Description                                                                                        | Risk Cat | Test Level |      |        |        |      |      |
|---------------|----------------------------------------------------------------------------------------------------|----------|------------|------|--------|--------|------|------|
|               |                                                                                                    |          | SR         | Unit | Int    | ST     | FAT  | UAT  |
| Performance   | TSDB design choices fail to meet performance standards set within the Docker compose environment.  | B        | \*\*\*     |      | \*     | \*\*   | \*\* | \*\* |
| Compatibility | TSDB suffers from integration issues within the Docker compose structure                           | A        | \*\*\*     |      | \*\*\* | \*\*   |      |      |
| Integrity     | Service fails to extract all the desired details from the data, resulting in loss of quality data. | C        | \*\*       | \*\* | \*\*\* | \*\*   |      |      |
| Compatibility | API additions fail to be implemented correctly within the IoTa interface.                          | C        | \*\*       |      | \*\*   | \*     | \*\* | \*\* |
| Parsing       | A required message format is not properly recognized by the service.                               | B        | \*\*       | \*\* |        |        |      |      |
| Connectivity  | Connection to related IoTa containers is inconsistent, resulting in lost data or functionality.    | C        | \*\*       |      | \*\*\* |        | \*\* | \*   |
| Interfacing   | API requests fail to call the correct methods within the service.                                  | C        | \*         | \*   | \*\*\* |        |      |      |
| Interfacing   | CLI scripts fail to execute correctly.                                                             | C        |            | \*   |        | \*\*\* | \*\* | \*   |

Legend for the table above:

| RC          | Risk class (from product and technical risk analysis, where A=high risk, B=average risk, C=low risk)                                                                    |
|-------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| SR          | Static Review of the various intermediary products (requirements, functional design, technical design). Checking and examining artefacts without executing the software |
| Unit        | Unit test and Unit integration test                                                                                                                                     |
| Integration | Integration tests (low level (L), high level(H))                                                                                                                        |
| FAT         | Functional acceptance test (alpha stage UAT)                                                                                                                            |
| UAT         | User acceptance test (Beta stage UAT)                                                                                                                                   |
| ST          | System test (functional scenario testing (F), system quality scenario testing (S))                                                                                      |
|            | Limited thoroughness of the test                                                                                                                                        |
|           | Medium thoroughness of the test                                                                                                                                         |
|          | High thoroughness of the test                                                                                                                                           |
| \<blank\>   | If a cell is blank, it means that the relevant test or evaluation level does not have to be concerned with the characteristic                                           |

# Test Levels

For this MTP the following test levels are acknowledged:

| **Test level**       | **Goal**                                                                                                                                                                                                                                       |
|----------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Unit testing:        | The aim is to test each part of the software by separating it. It checks that component are fulfilling functionalities or not                                                                                                                  |
| Integration testing: | In this testing phase, different software modules are combined and tested as a group to make sure that integrated system is ready for system testing. Integrating testing checks the data flow from one module to other modules.               |
| System testing:      | System testing is performed on a complete, integrated system. It allows checking system's compliance as per the requirements. It tests the overall interaction of components. It involves load, performance, reliability and security testing. |
| Acceptance testing:  | Acceptance testing is a test conducted to find if the requirements of a specification or contract are met as per its delivery.                                                                                                                 |

## The Unit Testing Level 

The primary goal of unit testing is to confirm the service understands
the message types it is required to work with.

### Entrance and Exit Criteria

Entry criteria for this section is having the message formats that will
be converted into the TSDB data points and the functions related to
them. Possibly even for pulling the data from the TSDB, but it may be
unlikely until integration testing.

Exit criteria is the messages are successful in being read by the
service, and the output is the data points that will be stored in later
stages of development.

### Test Environment

<span id="_Toc37168498" class="anchor"></span>Simple testing of
individual processes such as reading from example messages of the
formats present in the live environment in listening to RabbitMQ. This
would also include message tables from within the current FDT and IoTa
databases that would only be called with specific scripts.

### Test Objectives

| **Risk**                                                                                                          | **Test Goals**                                                                                                | **Risk Verification**                                                                                                                         | **Schedule**                                                             |
|-------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| Integrity: Service fails to extract all the desired details from the data, resulting in the loss of quality data. | Confirm for each message type, that the data is correct as per the messages.                                  | Check the resulting data for each message format is not lacking in details/data points.                                                       | During implementation of the functions related to handling messages.     |
| Parsing: A required message format is not properly recognized by the service.                                     | Ensure the desired message formats are handled correctly and are not rejected or extracted with invalid data. | Test each message type with examples either provided by DPI or created based on our understanding.                                            | During implementation of the functions related to handling messages.     |
| Interfacing: API requests fail to call the correct methods within the service.                                    | Ensure the API is calling the correct functions when it receives a request.                                   | Test each function of the API, and the different amounts of requested data to confirm the correct details are included in the function calls. | During implementation of the API, follows later than prior unit-testing. |

## The Integration testing Level 

The primary goal of integration testing is to confirm the service
interacts correctly with individual components of IoTa, and also the new
TSDB.

### Entrance and Exit Criteria

Entry criteria is to have the other components of the Docker compose
running, and ready to receive/send requests to the service.

Exit criteria is each individual component can properly interact with
the service in isolation between two of the components.

### Test Environment

Testing of functions will begin after the service has connected to the
related component to be tested. For example the API and the service will
be tested to confirm the requests reach the service and work as
expected.

The TSDB (possibly multiple) should likely be tested in conjunction with
the message parsing functionality.

### Test Objectives

| **Risk**                                                                                                       | **Test Goals**                                                                                                                        | **Risk Verification**                                                                                                                    | **Schedule**                                                                                            |
|----------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| Performance: TSDB design choices fail to meet performance standards set within the Docker compose environment. | Ensure the service can handle multiple messages and save them to the TSDB.                                                            | Setup the service with multiple messages to be saved to the TSDB. Check that all messages were saved to the TSDB and no data is missing. | During TSDB testing, as it will aid in decision making.                                                 |
| Compatibility: TSDB suffers from integration issues within the Docker compose structure                        | Ensure TSDB works within the Docker compose environment. Help identify best TSDB to be used.                                          | Setup the TSDB within the Docker compose image, and have it interact with the service via a service request.                             | During TSDB testing.                                                                                    |
| Integrity: Service fails to extract all the desired details from the data, resulting in loss of quality data.  | Ensure the desired details are retrieved from messages sent to the API and also IoTa DB CLI prompts.                                  | Check that correct data points are extracted from the data of each message type.                                                         | Can be tested alongside other RabbitMQ related message handling tests, and also after for CLI requests. |
| Compatibility: API additions fail to be implemented correctly within the IoTa interface.                       | Ensure the web interface is providing the API with sufficient detail for different methods.                                           | Check the output functions of the API based on what is done within the web interface.                                                    | Late stage testing, as it involves the IoTa interface and not key functionality.                        |
| Connectivity: Connection to related IoTa containers is inconsistent, resulting in lost data or functionality.  | Ensure there is no issue in the service that may result in dropped connections between container elements.                            | Perform an extended run for both streams of messages from the API, and also separately to the TSDB.                                      | Can be tested alongside other RabbitMQ related message handling tests.                                  |
| Interfacing: API requests fail to call the correct methods within the service.                                 | Test communication from the API to the service, to ensure that all method calls perform the right tasks and result in proper results. | Check data resulting from the method calls of the API, and see if the output is accurate to the data.                                    | Can be tested alongside other RabbitMQ related message handling tests.                                  |

## The System Testing Level 

The primary goal of system testing is to confirm the service interacts
correctly with all elements of IoTa working together. This is
essentially full use cases ran with the full architecture in place.

### Entrance and Exit Criteria

Entry criteria is to have the full set of Docker containers running, and
ready to receive/send requests to the service.

Exit criteria is each full use case results in the correct data being
stored and displayed, as well as scripts performing the correct tasks on
multiple systems.

### Test Environment

Testing of the service and TSDB in conjunction with the Docker
containers will be done by started at the beginning of each use case,
and following the full process to test each method within a close to
live environment.

The TSDB will likely be monitored further for performance issues, and if
there’s any issues with our design choices, or its capabilities within
this implementation.

### Test Objectives

| **Risk**                                                                                                       | **Test Goals**                                                                                     | **Risk Verification**                                                                                                                                                      | **Schedule**                                                                                                                                                                                           |
|----------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Performance: TSDB design choices fail to meet performance standards set within the Docker compose environment. | Check the performance of the TSDB schema, and if both retrieving and storing data is efficient.    | Check response times for each use case involving the TSDB. Determine if this is a result of the TSDB itself, or if another part of the system architecture is responsible. | Monitor during each run of a method within the full system, while other tasks are being performed.                                                                                                     |
| Compatibility: TSDB suffers from integration issues within the Docker compose structure                        | Identify if there is any issue in the TSDB compatibility within the full Docker compose structure. | Check if data is lacking any required details, or if the TSDB is simply not working as intended during specific operations.                                                | Monitor during each portion of a method test that interacts with the TSDB.                                                                                                                             |
| Integrity: Service fails to extract all the desired details from the data, resulting in loss of quality data.  | Check the output of the service within the TSDB within the full test environment.                  | Following message processing, check for invalid data within the TSDB, may also be worth checking output within the web interface after retrieval of data.                  | First part of the system test, a follow-up to population of database using RabbitMQ messages sent to the service.                                                                                      |
| Compatibility: API fails to be implemented correctly within the IoTa interface.                                | Confirmation of the API functionality during the live environment.                                 | Check the output of queries from the user interface to the API, and confirm data, and ranges of data is accurate to the request.                                           | Second part of the test, relies on the database storing the correct data.                                                                                                                              |
| Interfacing: CLI scripts fail to execute correctly.                                                            | Check functionality and reliability of scripts during the service running.                         | Confirm function of IoTa database table import into TSDB. Confirm backup scripts perform relevant functions, and work without issue.                                       | Can be done at any point after beginning of System testing. Backup restore should likely be done after testing of live environment, unless it is intended to work that way and import lost data later. |

## The Acceptance Testing Level 

The primary goal of acceptance testing is to confirm the service meets
the specific requirements set by DPI through testing with the purpose of
receiving their feedback.

### Entrance and Exit Criteria

Entry criteria is the system testing is successful, and is ready to be
presented to the stakeholders to determine if there is any issue, or
missing functionality.

Exit criteria is confirmation by DPI that the service, TSDB, and API
implementation meets the requirements that they have set, and the work
is of a high standard.

### Test Environment

Either presenting the test to stakeholders via a stream, or providing
them with our repo to test on their own system, and we can advise on how
to interact with the system either live or using a guide.

### Test Objectives

| **Risk**                                                                                                       | **Test Goals**                                                                                                             | **Risk Verification**                                                                                                                   | **Schedule**                                                                         |
|----------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
| Performance: TSDB design choices fail to meet performance standards set within the Docker compose environment. | To verify if that design is acceptable by the stakeholder’s standards, or clash with an existing part of the architecture. | Check with stakeholders if there is any concern regarding a specific design element, or performance metric that is related to the TSDB. | Following some demoing of the use cases.                                             |
| Compatibility: API additions fail to be implemented correctly within the IoTa interface.                       | To verify by the stakeholders standards that no issue is occurring between the API and expected functionality.             | Have the stakeholders try multiple inputs that would be often used during production, and check results.                                | Following the database being populated with messages.                                |
| Connectivity: Connection to related IoTa containers is inconsistent, resulting in lost data or functionality.  | To verify connection between the service and related elements experiences no issues with DPI’s setup.                      | Verify all data flows remain uninterrupted, and nothing is lost during stakeholder test.                                                | Should be checked throughout acceptance test to verify actions as they’re performed. |
| Interfacing: CLI scripts fail to execute correctly.                                                            | Confirm functionality of each script is sufficient for the needs of DPI.                                                   | Have the stakeholders run through the scripts and confirm options are sufficient, and results are as expected.                          | Performed at the end of acceptance test.                                             |

