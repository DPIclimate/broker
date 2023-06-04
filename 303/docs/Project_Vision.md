# Introduction

The Department of Primary Industries (DPI) has an existing Internet of
Things (IoT) system called IoTa that allows a series of physical and
remote sensors to be monitored via messages and stored into a database.
These messages include time-series data of multiple types captured by
these sensors, that is used for the purpose of data analysis.

The goal of this project is to simplify and enhance usage of the system
through integration of a Time-series database (TSDB) that will allow for
better handling of time series data, both in storage and retrieval.

This will involve maintaining the current Docker compose setup, allowing
messages used by the IoTa to be parsed and stored into the new TSDB
using an output service, and introducing an application programming
interface (API) similar to the existing REST API so that the TSDB’s data
may be retrieved and analysed allowing for better aggregation of data
than currently possible. An additional integration into the existing web
app will also be performed, to allow for visualisation of the time
series data.

Our main goal is to implement these features into IoTa to fulfil the
functional and nonfunctional requirements set by DPI, however, in order
to ensure the best possible fulfilment of these requirements we have
also opted to assess multiple TSDBs. There are several TSDB
implementations available, each having a range of varied
characteristics, and so some amount of analysis is required for us to be
able to say with confidence we have selected the right implementation.

The following document along with the master test plan go into further
detail on the requirements of TSDB, however as a broad stroke, we will
partially be implementing Timescale, QuestDB, InfluxDB, PrometheusDB and
testing them against our master test plan.

# Positioning

## Problem Statement

There are several problems affecting the current system that can be
resolved through the implementation of this project. The problems relate
to how the current system is overly complex, uses an unoptimised
database system for the types of data used, and data could be accessed
differently to allow better visualisation and analysis.

<table>
<colgroup>
<col style="width: 31%" />
<col style="width: 68%" />
</colgroup>
<thead>
<tr class="header">
<th><blockquote>
<p>The problem of</p>
</blockquote></th>
<th>Having having existing database tables containing old data</th>
</tr>
<tr class="odd">
<th><blockquote>
<p>affects</p>
</blockquote></th>
<th>The complexity of the system and the ability to analyse stored
data</th>
</tr>
<tr class="header">
<th><blockquote>
<p>the impact of which is</p>
</blockquote></th>
<th>Increased complexity in retrieving the data, resulting in difficulty
for access to access and analyse the data if it is in more than one
format/database.</th>
</tr>
<tr class="odd">
<th><blockquote>
<p>a successful solution would be</p>
</blockquote></th>
<th>Implementing a system that can turn database table data back into
IoTa message format, and also process that message into the new TSDB.
This will allow for increased time-related aggregation of data, and
potential to visualise the data, providing better tools for
analysis.</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

<table>
<colgroup>
<col style="width: 32%" />
<col style="width: 67%" />
</colgroup>
<thead>
<tr class="header">
<th><blockquote>
<p>The problem of</p>
</blockquote></th>
<th>Using a standard relational database for time series data</th>
</tr>
<tr class="odd">
<th><blockquote>
<p>affects</p>
</blockquote></th>
<th>Project scalability, performance and ability to query the database
(retrieve the data), ability to analyse the data, size of space
used</th>
</tr>
<tr class="header">
<th><blockquote>
<p>the impact of which is</p>
</blockquote></th>
<th>Difficulty in retrieving data between timestamps and options for
aggregation are limited. Low performance retrieval speeds and
inefficient storage, as a result of being unoptimised for time-series
data.</th>
</tr>
<tr class="odd">
<th><blockquote>
<p>a successful solution would be</p>
</blockquote></th>
<th>Having a local TSDB storing all the data such that it becomes
trivial to make time series related queries for analysing the data,
along with gaining the benefits of performance/storage/ease of use that
would come with using a time series optimised database.</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

<table>
<colgroup>
<col style="width: 32%" />
<col style="width: 67%" />
</colgroup>
<thead>
<tr class="header">
<th><blockquote>
<p>The problem of</p>
</blockquote></th>
<th>Using an external cloud based platform for time series data</th>
</tr>
<tr class="odd">
<th><blockquote>
<p>affects</p>
</blockquote></th>
<th>Privacy, security, downtime and costing of the system</th>
</tr>
<tr class="header">
<th><blockquote>
<p>the impact of which is</p>
</blockquote></th>
<th>Additional costs involved in storage of data in an online database,
and by hosting it on a third party, there is a chance that the privacy
and security of the data could be compromised, as well as missed
messages due to network issues. It has been noted that if the online
service goes down then it affects IoTa.</th>
</tr>
<tr class="odd">
<th><blockquote>
<p>a successful solution would be</p>
</blockquote></th>
<th>Self hosting a TSDB to both save running costs, and ideally increase
the privacy and security of the stored data.</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

##  

## Product Position Statement

DPI requires a simpler platform that is better suited for the type of
data that is managed by this application. By implementing the TSDB
system, the scalability and the ease of use will increase, along with
the improved output data allowing better visualisation and analysis.

<table>
<colgroup>
<col style="width: 17%" />
<col style="width: 82%" />
</colgroup>
<thead>
<tr class="header">
<th><blockquote>
<p>For</p>
</blockquote></th>
<th>DPI</th>
</tr>
<tr class="odd">
<th><blockquote>
<p>Who</p>
</blockquote></th>
<th>Would like to retrieve data with respect to time.</th>
</tr>
<tr class="header">
<th><blockquote>
<p>The TSDB</p>
</blockquote></th>
<th>is a local time series database implementation.</th>
</tr>
<tr class="odd">
<th><blockquote>
<p>That</p>
</blockquote></th>
<th>Optimally stores and retrieves time series data.</th>
</tr>
<tr class="header">
<th><blockquote>
<p>Our product</p>
</blockquote></th>
<th>Is much better suited to time series data over relational
databases.</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

<table>
<colgroup>
<col style="width: 17%" />
<col style="width: 82%" />
</colgroup>
<thead>
<tr class="header">
<th><blockquote>
<p>For</p>
</blockquote></th>
<th>DPI</th>
</tr>
<tr class="odd">
<th><blockquote>
<p>Who</p>
</blockquote></th>
<th>Would like to compact their data into a single format and
database.</th>
</tr>
<tr class="header">
<th><blockquote>
<p>The TSDB</p>
</blockquote></th>
<th>is a time series database implementation with python
microservice.</th>
</tr>
<tr class="odd">
<th><blockquote>
<p>That</p>
</blockquote></th>
<th>Would allow current and older messages to be converted and stored in
the one system.</th>
</tr>
<tr class="header">
<th><blockquote>
<p>Our product</p>
</blockquote></th>
<th>Would simplify the system, and allow trivial extraction of
data.</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

<table>
<colgroup>
<col style="width: 17%" />
<col style="width: 82%" />
</colgroup>
<thead>
<tr class="header">
<th><blockquote>
<p>For</p>
</blockquote></th>
<th>DPI</th>
</tr>
<tr class="odd">
<th><blockquote>
<p>Who</p>
</blockquote></th>
<th>Would like to maintain their current container implementation.</th>
</tr>
<tr class="header">
<th><blockquote>
<p>The TSDB</p>
</blockquote></th>
<th>Will be implemented into the existing docker compose stack, and work
with the current system.</th>
</tr>
<tr class="odd">
<th><blockquote>
<p>That</p>
</blockquote></th>
<th>Allows implementation of this new system without impacting the
current system</th>
</tr>
<tr class="header">
<th><blockquote>
<p>Our product</p>
</blockquote></th>
<th>Would not impact the current ecosystem</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

# 

# Stakeholder Descriptions

## Stakeholder Summary

<table>
<colgroup>
<col style="width: 18%" />
<col style="width: 34%" />
<col style="width: 46%" />
</colgroup>
<thead>
<tr class="header">
<th><strong>Name</strong></th>
<th><strong>Description</strong></th>
<th><strong>Responsibilities</strong></th>
</tr>
<tr class="odd">
<th>DPI staff (user)</th>
<th>DPI and staff therein that will be working with the time series
database and data within from associated probes and sensors across the
state.</th>
<th><p>Make use of the IoTa system for the purposes of data
analysis.</p>
<p>Modify sensor pairings and add additional sensors that will need to
be recorded within the database.</p></th>
</tr>
<tr class="header">
<th>DPI development team</th>
<th>DPI’s internal team that develops the current IoTa system. They are
currently overseeing our development.</th>
<th><p>Monitors the project’s progress</p>
<p>Provides insight and input where required for decision making</p>
<p>Ensures project is addressing major requirements</p>
<p>Ensures constraints with existing technologies are known and
met</p></th>
</tr>
<tr class="odd">
<th>Our Team</th>
<th>All four members of our development team. Will be working on the
project over the course of a year.</th>
<th><p>Adhere to requirements set by DPI contacts.</p>
<p>Gain the knowledge required to develop each requirement of the
project.</p>
<p>Develop each use case and embed it into the existing
architecture.</p>
<p>Test each aspect of the project to ensure proper functionality.</p>
<p>Provide documentation on final implementation.</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

##  

## User Environment

***<u>Working Environment</u>***

There are no more than a few hundred sensors, resulting in a message
every five seconds. There are no real performance constraints and it is
not believed that the number of actions will increase dramatically
enough to cause performance issues.

***<u>Unique Constraints</u>***

The physical sources can change at any moment but the logical source
must remain constant. This is linked manually via CLI. These pairings
will also be stored within the new TSDB, and will allow for changing of
logical source due to moving of devices, rather than replacement.

Must run inside current docker compose stack

TSDB must run inside a container, and be self hosted.

***<u>Existing System:</u>***

IoTa is a python microservice environment running on Linux. Data enters
IoTa via external messages from TTN and REST APIs through HTTP/s.

The incoming messages are stored before any processing to limit loss
from system failure and are then converted to an internal message format
and are handled by RabbitMQ in a fan out messaging style.

The physical sources can change at any moment however the logical source
is linked to the replaced source via the Device Mapper.

The data is stored in a local postgreSQL database, and also a
cloud-based platform called Ubidots.

IoTa is implemented through Python, with some shell scripts for
automation, it is deployed on a docker compose stack.

There is a legacy FDT system that uses a different database structure
and message format. This is no longer in use but the data still exists
within a database.

***<u>TSDB System:</u>***

The TSDB system will need to interact with existing technology stack
(docker compose), the current IoTa messaging format (JSON), the current
IoTa database, and implement an API for retrieving data in the various
forms provided by the TSDB. We are not replacing Ubidots for time series
data at this time, but this may be a long term goal for DPI.

The most active component of this system will be an output service that
will run within a Docker container. The purpose of this is to receive
messages from the RabbitMQ container and process them into the TSDB.
This will include parsing IoTa messages into that which the TSDB can
store. We will also need to allow for conversion of IoTa database tables
back into IoTa message format, for the purpose of processing them.

At the basis of this is the TSDB itself. Also stored within a container
will interact with both the output service and the API. Details of the
environment will depend on the chosen TSDB, however it will serve the
same purpose regardless.

The API is the primary section of the system that will be interacted
with by the user. This will be responsible for sending queries to
retrieve data from the TSDB, and providing the ability to aggregate the
data into varying forms, for example, averages over a time period.

Scripts will be used via CLI that will allow for backup creation and
restoration.

The existing web app will be modified to allow for a way to display data
using a visual graph representation. This will likely be done through
either the chosen TSDB’s interface or software such as Grafana if
necessary.

# Product Overview

## Needs and Features

| **Need**                                                             | **Priority** | **Features**                                                                                                                                                                | **Planned Release** |
|----------------------------------------------------------------------|--------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------|
| Store data in an efficient and optimal way                           | 1            | Time Series Database (TSDB) implementation: Optimised for handling time series data such that it will be used with the system allows for easier use, scaling and retrieval. | Construction Phase  |
| Retrieve data from the system                                        | 2            | Python API for TSDB implementation: Ability to query database for records within a specified time period                                                                    | Construction Phase  |
| Store incoming sensor data                                           | 1            | Python Microservice and TSDB: Extract data from new messages and store into TSDB                                                                                            | Elaboration Phase   |
| To be able to still access and use existing/old IoTa database tables | 3            | Python Microservice: Convert existing IoTa messages into IoTa internal messaging format.                                                                                    | Construction Phase  |
| Ability to import existing data from IoTa DB into TSDB               | 3            | Python Microservice and TSDB: Store converted IoTa messages into TSDB                                                                                                       | Construction Phase  |
| To be able backup and restore the database                           | 4            | Shell scripts to easily back up and restore the TSDB                                                                                                                        | Construction Phase  |
| Must not utilise cloud hosting                                       | 4            | Time Series Database implementation: Self hosted and containerised implementation                                                                                           | Elaboration Phase   |
| Compatibility with existing implementation                           | 1            | Runs inside existing technology.                                                                                                                                            | Elaboration Phase   |
| Graphical representation of data within a web app.                   | 4            | Allow for aggregation of time-series data, and display it graphically.                                                                                                      | Construction Phase  |

# 

# Time Series Database Criteria:

| **Metric**                          | **Importance** | **Description**                                                                                                                                                      |
|-------------------------------------|----------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Storage efficiency/Data compression | 1              | High importance for scalability reasons. The ability to compress data, while still providing good retrieval speed.                                                   |
| Ability to visualise data           | 1              | High importance as it is a requirement. If lacking innate capability to visualise, then the ability to implement an option to visualise data should be investigated. |
| Retrieval efficiency                | 2              | Ability to aggregate data according to time-related criteria at a reasonable speed. Can be affected by the DBs techniques for data storage.                          |
| Usability                           | 2              | The ease of which to both customise the database, and perform effective queries. Documentation may affect this.                                                      |
| Write performance                   | 3              | Speed at which data is written. Low importance due to expectation of roughly consuming messages every 5 seconds.                                                     |

# 

# Other Product Requirements

<table>
<colgroup>
<col style="width: 49%" />
<col style="width: 14%" />
<col style="width: 35%" />
</colgroup>
<thead>
<tr class="header">
<th><strong>Requirement</strong></th>
<th><strong>Priority</strong></th>
<th><strong>Planned Release</strong></th>
</tr>
<tr class="odd">
<th><p><em>Security:</em></p>
<p>TSDB and API implementations should only be accessed by authorised
users, user restrictions should be based on role.</p></th>
<th>1</th>
<th>Construction Phase</th>
</tr>
<tr class="header">
<th><p><em>Robustness</em>:</p>
<p>TSDB: Should be available at all hours for input data to be stored or
retrieved.</p>
<p>TSDB: Must store both physical and logical ID mappings, with ability
to update either.</p>
<p>API: Should be able to reliably parse incoming and existing
messages</p></th>
<th>1</th>
<th>Construction Phase</th>
</tr>
<tr class="odd">
<th><p><em>Fault Tolerance:</em></p>
<p>Data stored and retrieved should be accurate and expected</p></th>
<th>1</th>
<th>Construction Phase</th>
</tr>
<tr class="header">
<th><p><em>Usability:</em></p>
<p>The system should be at least as easy as the current implementation
in both deployment and ongoing use.</p></th>
<th>2</th>
<th>Transition Phase</th>
</tr>
<tr class="odd">
<th><p><em>Documentation:</em></p>
<p>TSDB schema should be documented</p>
<p>TSDB restore/backup scripts to be documented</p>
<p>API usage should be documented</p></th>
<th>3</th>
<th>Construction Phase</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

| **Constraint**                                                        | **Priority** | **Planned Release** |
|-----------------------------------------------------------------------|--------------|---------------------|
| Receive messages from RabbitMQ                                        | 1            | Elaboration Phase   |
| Runs inside a docker container and added current docker compose stack | 1            | Elaboration Phase   |
| Implemented in Python                                                 | 1            | Elaboration Phase   |
| Uses Python image provided by DPI                                     | 1            | Elaboration Phase   |

# Document Changelog

13/05/23:

- Removed/Changed references from FDT to IoTa DB, as requirement is
  > removed by stakeholder.

- Clarified in “needs and features” that conversion of old DB messages
  > is performed via a CLI script.

- Added a new requirement regarding mapping of physical and logical IDs
  > under “Robustness”.

- Modified constraint release to elaboration phase, as they’ve been
  > dealt with.

14/05/23:

- Clarified “Move away from cloud hosting” to “Must not utilise cloud
  > hosting” in multiple instances, as the current system is also local.

- Added phases to planned release sections within “needs and features”,
  > and “other product requirements” sections.

- Added additional stakeholder entities, including our team, and
  > separated DPI dev team from general staff.

- Various modifications to wording and sentence structure.

- Removed some leftover numbering for sections from the template.

15/05/23:

- Removed problem statement “Using external cloud based database”.

- Expanded on the TSDB system under User Environment.

- Minor modifications to wording and sentence structure in User
  > Environment.

- Separated “implemented in python”, and “using DPIs python image” in
  > constraints.

22/05/23:

- Re-added problem of cloud DB, as clarified that Ubidots offers similar
  > function as one. Changed the context as we are not replacing it at
  > this time, just adding our own TSDB in addition to the current
  > system.

- Also added reference to this in the existing system.

- Added multiple details/references to the requirement of graphical
  > representation of data within a web app.

24/05/23

- Changed references in Positioning from dealing with multiple message
  > formats to dealing with existing database tables that will need to
  > be imported.

- Updated some textual clarifications in Positioning.

- Updated structure of document.

> 25/05/23

- Added addition to introduction including TSDB. (credit to Callum)

> 30/05/23

- Added TSDB criteria under product overview.
