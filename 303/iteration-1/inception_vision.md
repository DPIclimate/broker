| **DPI: IoTa Time Series Database** | |
| --- | --- |
| Inception Project Vision | Date: 27/03/23 |

**DPI IoTa Time Series Database**

** Vision **
#
# 1. Introduction

The Department of Primary Industries (DPI) has an existing Internet of Things (IoT) system called IoTa that allows a series of physical and remote sensors to be monitored via messages and stored into a database. There is also an older system known as FDT, which uses a different database with different structures.

The goal of this project is to simplify the system by using a TSDB that is better at handling time series data, move away from a cloud based database by instead hosting it inhouse, allow previous messages used by both IoTa and FDT to be converted and stored into the new TSDB and include an application programming interface (API) so that the TSDB's data may be retrieved and analysed.

#
# 2. Positioning
### 2.1 Problem Statement

There are several problems affecting the current system that can be resolved through the implementation of this project. The problems relate to how the current system is overly complex, uses an unoptimised database system for the types of data used, and data could be accessed differently to allow better visualisation and analysis.

| The problem of | _Having multiple message formats and databases_ |
| --- | --- |
| affects | _The complexity of the system and the ability to analyse stored data_ |
| the impact of which is | _Complexity means more time for testing, more time implementing changes and more time for retrieving the data. It becomes harder to access and analyse the data if it is in more than one format/database._ |
| a successful solution would be | _Having a simplified system where data can be accessed from a single system and be formatted such that analysing/visualising it is easier and any future changes would have less overall impact from existing systems._ |
##
| The problem of | _Using a relational database for time series data_ |
| --- | --- |
| affects | _Project scalability, performance and ability to query the database (retrieve the data), ability to analyse the data, size of space used_ |
| the impact of which is | _That currently, it is difficult to retrieve data between timestamps, performance at storing and retrieving data by using a database that is not optimised for time series data is lowered._ |
| a successful solution would be | _Having a single TSDB storing all the data such that it becomes trivial to make time series related queries for analysing the data, along with gaining the benefits of performance/storage/ease of use that would come with using a time series optimised database._ |
##
| The problem of | _Using external cloud based database_ |
| --- | --- |
| affects | _Privacy, security and costing of the system_ |
| the impact of which is | _It is likely that there is a costing involved by storing data in an online database, and by hosting it on a third party, there is a chance that the privacy and security of the data could be compromised_ |
| a successful solution would be | _Self hosting the TSDB to both save running costs, and ideally increase the privacy and security of the stored data._ |

##

### 2.2 Product Position Statement

DPI requires a simpler platform that is better suited for the type of data that is managed by this application. By implementing the TSDB system, the scalability and the ease of use will increase, along with the improved output data allowing better visualisation and analysis.

| For | _DPI_ |
| --- | --- |
| Who | _Would like to retrieve data in a more time oriented way_ |
| The TSDB | _is a_ time series database implementation |
| That | _Optimally stores and retrieves time series data_ |
| Our product | _Is much better suited to time series data over existing relational databases._ |
##
| For | _DPI_ |
| --- | --- |
| Who | _Would like to compact their data into a single format and database_ |
| The TSDB | _is a time series database implementation with python microservice_ |
| That | _Would allow current and legacy messages to be converted and stored in the one system_ |
| Our product | _Would simplify the system, and allow trivial extraction of data._ |
##
| For | _DPI_ |
| --- | --- |
| Who | _Would like to not disrupt their current implementation_ |
| The TSDB | _Would run inside existing docker compose stack, and work with current system_ |
| That | _Would allow implementation of this new system without impacting the current system_ |
| Our product | _Would not impact the current ecosystem_ |

##
# 3. Stakeholder Descriptions
### 3.1 Stakeholder Summary

| **Name** | **Description** | **Responsibilities** |
| --- | --- | --- |
| DPI | DPI and staff therein that will be working with the time series database and data within from associated probes and sensors across the state. | -- Monitors the project's progress. -- Provides insight and input where required for decision making. -- Ensures project is addressing major requirements. -- Ensures constraints with existing technologies are known and met |

### 3.2 User Environment

<u> ***Working Environment*** </u>

There are (believed to be) no more than a few hundred sensors, resulting in a message per 5 seconds. There are no real performance constraints and it is not believed that the number of actions will increase dramatically enough to cause performance issues.

<u> ***Unique Constraints*** </u>

-- The physical sources can change at any moment but the logical source must remind constant, this is linked manually via CLI.

-- Must run inside current docker compose stack

-- TSDB must run inside a container, and be self hosted.

<u> ***Existing System:*** </u>

-- IoTa is a python microservice environment running on Linux. Data enters IoTa via external messages from TTN and REST APIs through HTTP/s.

-- The incoming messages are stored before any processing to limit loss from system failure and are then converted to an internal message format and are handled by RabbitMQ in a fan out messaging style.

-- The physical sources can change at any moment however the logical source is linked to the replaced source via Device Mapper.

-- The data is stored in a postgresql database.

-- IoTa is implemented through Python, with some shell scripts for automation, it is deployed on a docker compose stack.

-- There is a legacy FDT system that uses a different database structure and message format.

<u> ***TSDB System:*** </u>

The TSDB system will need to interact with existing technology stack (docker compose), the legacy FDT and the current IoTa messaging formats, the legacy FDT database and current IoTa database, and run an API for retrieving data.
#
# 4. Product Overview
### 4.1 Needs and Features

| **Need** | **Priority** | **Features** | **Planned Release** |
| --- | --- | --- | --- |
| Store data in an efficient and optimal way | 1 | Time Series Database (TSDB) implementation: Optimised for handling time series data such that it will be used with the system allows for easier use, scaling and retrieval. | TBC |
| Retrieve data from the system | 2 | Python API for TSDB implementation: Ability to query database for records within a specified time period | TBC |
| Store incoming sensor data | 1 | Python Microservice and TSDB: Extract data from new messages and store into TSDB | TBC |
| To be able to still access and use existing FDT system | 3 | Python Microservice: Convert existing FDT and IoTa messages into IoTa internal messaging format | TBC |
| To be able to move existing data from FDT over | 3 | Python Microservice and TSDB: Store converted FDT and IoTa messages into TSDB | TBC |
| To be able backup and restore the database | 4 | Shell scripts to easily back up and restore the TSDB | TBC |
| Move away from cloud hosting | 4 | Time Series Database implementation: Self hosted and containerised implementation | TBC |
| Compatibility with existing implementation | 1 | Runs inside existing technology. | TBC |

#
# 5. Other Product Requirements

| **Requirement** | **Priority** | **Planned Release** |
| --- | --- | --- |
| _Security:_ TSDB and API implementations should only be accessed by authorised users, user restrictions should be based on role. | 1 | TBC |
| _Robustness_: TSDB: Should be available at all hours for input data to be stored or retrieved. API: Should be able to reliably parse incoming and existing messages | 1 | TBC |
| _Fault Tolerance:_ Data stored and retrieved should be accurate and expected | 1 | TBC |
| _Usability:_ The system should be at least as easy as the current implementation in both deployment and ongoing use. | 2 | TBC |
| _Documentation:_ TSDB schema should be documented TSDB restore/backup scripts to be documented API usage should include man pages | 3 | TBC |

| **Constraint** | **Priority** | **Planned Release** |
| --- | --- | --- |
| Receive messages from RabbitMQ | 1 | TBC |
| Runs inside docker container provided by DPI and added current docker compose stack | 1 | TBC |
| Implemented in Python | 1 | TBC |

| Confidential | © Team 3, 2023 | Page 0 |
| --- | --- | --- |
```

