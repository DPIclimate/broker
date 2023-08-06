--- 

#### DPI: IoTa Time Series Database

# Architecture Notebook
---

## Purpose

This document describes the philosophy, decisions, constraints,
justifications, significant elements, and any other overarching aspects
of the system that shape the design and implementation of the Time
Series Database for the NSW Department of Planning and Industry's IoTa
project.

## Architectural goals and philosophy

The Department of Planning and Industry launched a "Climate Smart
Pilots" project for the Digital Agriculture team, specifically to
observe the impact of digital agriculture strategies on reducing climate
change. The secondary goal of the project was to explore the current
usages of agriculture technologies, and how they can be incorporated
into existing Australian farming practices.

The project was started in 2018 and contains several pilot sites all
over NSW. These sites contain various sensors: salinity, soil health,
temperature, humidity, weather stations etc, which gather data from the
sensors. DPI have identified a number of issues that their IoTa is to
address, these include multiple communications protocols, varying
message formats, replacement of real world devices, redundant message
processing, management and monitoring services \[1\].

Currently IoTa runs inside a Docker Compose stack, it is made up of
around a dozen Docker containers, the majority of these are running
Python modules which can be handled by their BrokerCLI.py module. Our
proposed addition to the IoTa stack is to add additional Python modules
to the existing Python image base to run alongside the existing
architecture. We will need to add two additional python modules in order
to abide by microservice architecture rules of having each module do a
specific 'thing', one of these modules is to process incoming messages,
the other will function as an API \[2\].

Much like the existing Postgres database, our (to be chosen) Time Series
Database (TSDB) will run inside its own container also inside the
compose stack. For the remaining document TSDB simply refers to a time
series database implementation. Our goal is to partially implement
multiple TSDB for review and testing, and then choosing the best fit, at
this stage QuestDB, InfluxDB, TimeScale and Prometheus are in the
running. There should be little architectural differences between any of
the databases in the eyes of this document. Incoming messages will need
to be processed and inserted into the TSDB, and an API will retrieve the
data. Whilst the selection of the correct database is important, we do
not consider it to be the CCRD, the main goal of this project is to add
a functioning TSDB to the IoTa project, and thus that is considered the
CCRD \[3\].

The main goal of the Time Series database team is to reduce dependency
on third-party IoT time series database platforms, and to migrate the
existing data collection system to a custom-built time series database
solution hosted on the DPI network. By using a self hosted time series
database solution, the team will be able to customize the feature-set of
the database to integrate all the data in their expected format.

After review of the current system, and talks with DPI team, several
common themes that will drive decision making regarding architecture
have been identified \[4\]:

-   Space Requirements: With all IoT sensor monitoring workloads, size will continue to increase steadily. Currently the backup file for around six months of use is uncompressed \~11GB, and so we will need to ensure data is compressed and possibly implement a data retention policy.

-   Robustness: This is one of the more important constraints, we need to ensure a high uptime and automatic recovery in case of the container failing.

-   Legacy Systems: IoTa is an ongoing project with a web of infrastructure already in place to retrieve and deploy sensor data. It is imperative that the new time series database backend is made compatible with the existing framework.

-   Redundancy: This does not appear to be a major concern, the implemented TSDB will be able to be built again from the stored messages in the existing Postgres database.

-   Security: Security has not been deemed an overly important aspect, by ensuring our API and TSDB are handled correctly we can cover the security concerns.

-   Performance: This does not appear to be a major concern in that any chosen TSDB will safely handle the load, and per the restraints given to us, we only need to process a single message at a time. Currently the team DPI have conveyed that the system processes a message every few seconds,

-   We do not need to worry about the possible future Kubernetes transition for this project.

3.  ## Assumptions and dependencies

    1.  ####  Assumptions \[5\]

-   The team either has the skills required or will be able to learn the skills required to develop and deploy a time series database solution.

-   Ben and David will be available to assist the team with any questions they have about the project, and to provide guidance on architectural requirements, constraints, and decisions.

-   The number of devices will not increase tenfold over a short period of time.

-   We do not need to process unformatted messages.

-   There may be different time series data in the future.

-   We will try to keep our 'master' in sync with DPI IoTa 'master' to ensure that final merging is as easy as possible.

-   LTSReader.py is the provided 'skeleton code'

-   We only need to concern ourselves with \`logical_timeseries\` data, and can use existing postgres table that contains mapping information \[17A\]

    1.  #### Dependencies \[6\]

-   Our receiver will handle incoming messages using the existing internal IoTa message format.

-   Our receiver, API, and TSDB will run inside the current docker compose stack in their own containers.

-   We require the front and mid tier processes to process incoming messages and send the data to the exchanges.

-   We will need to store both physical and logical time series data.

-   We need to implement a way to back up and restore the TSDB.

-   We need to be able to copy existing data into TSDB.

#  

## Architecturally significant requirements \[7\]

This project can be broken up to into three separate subsections:

**Receiver:**

-   Must handle varying messages in the existing IoTa internal formatting (JSON).

-   Must use a unique id based off the mapping of the logical and physical devices, this exists in postgres currently \[17A\]

-   Must use the existing queue/exchange system (RabbitMQ).

-   Uses Python implementation.

-   Run inside the container.

**TSDB:**

-   Have a unique way to identify the time series data not linked to *p_uid* or *l_uid*.

-   Run inside the container.

-   Compression of data.

-   Ability to have backup and restore via bash scripts.

-   Ability to implement data retention policy if required.

**API:**

-   Uses Python implementation.

-   Can retrieve data from the database between two given times.

-   Output varying data such as JSON, CSV.

-   Usable from within a CLI.

-   Run inside the container.

-   Appropriate CLI documentation.

**Scripting**

-   Handle backup and restore functionality for TSDB.

-   Handle converting existing IoTa table data into IoTa msg and insert into TSDB.

## Decisions, constraints, and justifications \[8\]

-   Ensure that all aspects of the system are implemented in the current IoTa framework (docker compose stack) and that integrate well with the existing architecture.

    -   This project must be merged with IoTa so that the implemented features can be used.

    -   The features of our project should not disrupt the existing flow or usage of IoTa.

-   API will use FastAPI as the third party library.

    -   IoTa already uses this library (RestAPI, Webhook), so it does not increase dependencies, and FastAPI is a top rated library for APIs.

-   API for retrieving data from TSDB should have some ability to choose output and have varying inputs.

    -   The API must be usable in production/the real world.

-   Generic processing of the incoming messages.

    -   The time series data can change between messages, sensors may have more than one time series data that they record) or time series data can change over time.

-   Use existing incoming message protocols - a queue via RabbitMQ.

    -   This is a hard requirement according to the original specifications, it also makes the most sense due to the existing architecture of IoTa using RabbitMQ and publishing messages.

-   TSDB to be self-hosted and also run inside the container system.

    -   This is a hard requirement according to the original specifications, this also makes the most sense due to the microservice architecture of IoTa, and its simplicity to run everything linked into a single docker compose stack.

-   Use provided skeleton code for receiving messages from IoTa (presumed to be LTSReader.py).

    -   This is a hard requirement according to the original specifications, also is the best way to implement.

-   Ensure there is some sort of health check on the services we implement.

    -   Currently all the services have a health check, so ours should follow the existing designs.

-   Some level of authentication is required.

    -   Ideally setting password inside the existing .env file, much like is already done, however depending on which TSDB is used, authentication may vary.

#  

## Architectural Mechanisms \[9\]

IoTa currently uses a microservice architecture approach, which are
currently broken down into three areas: Front-End, Mid-Tier and
Back-End. It also uses a publish/subscribe type pattern for passing
messages through the system.

Currently all internal messages are handled via RabbitMQ message broker
via the use of exchanges. This allows more than one process to receive a
message by subscribing to the exchange, and means extra processes can be
added/removed without impacting the other processes

<u>Red indicates new processes, whilst black is for existing.</u>

**<u>[Component View: \[17A\]</u>**

![](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/docs/media/component_diagram.png?raw=true)

#### Front-End processors \[10\] 

TTN WEBHOOK, REST API POLLERS, RABBITMQ : these receive messages before
they are processed by IoTa

TTN DECODER, RABBITMQ POLLERS : these convert messages into IoTa format
and send them through to mid-tier processes

Front end processors are responsible for creating physical devices, and
storing the received messages (raw_message) and the physical device into
the IoTa Postgres DB

POSTGRES DECODER \[17A\] : Note this feature has now been tabled
(pending DPI team), however there may be some variation added before
final release so it shall remain in document. If it does get
implemented, then it might be possible to use 'broker_correlation_id' to
reconstruct the IoTa internal format from the existing IoTa data without
needing to fully reprocess the raw messages.

This is a new front-end processor that we will implement to enable us to
be able convert a existing postgres data into IoTa message format and
allow us to send it to an exchange such as 'existing_timeseries' so that
existing messages can can passed onto TSDB with duplicate processing
from logical_timeseries or similar.

#### Mid-Tier processor \[11\]

DEVICE MAPPER / LOGICAL MAPPER : this is the only existing mid-tier
process, it monitors the physical time series exchange and handles
mapping of a physical device to a logical device (creates/drops messages
or devices as required).

#### Back-End processors \[12\]

The back-end processors are responsible for writing time series data to
destinations such as IoT platforms or locally hosted time series
databases.

IoTa uses two main exchanges via RabbitMQ message broker, these are
\`physical_timeseries\`(mid-tier) and \`logical_timeseries\`(back end),
we need to concern ourselves with only the logical exchange.\[17A\]

UBIDOTS WRITER : write time series data to Ubidots.

IOTA DECODER : we will need to implement an additional processor that
handles messages incoming into the logical, there will need to be some
processing to convert the IoTa internal json message to an insertable
format for our chosen TSDB. \[17A\]

The two likely scenarios for inserting data(TSDB dependent) are via Line
Protocol which is supported by various TSDB, otherwise it could be an
SQL type insert query, in either case, message processing is required.

The other factor to consider when processing a message is the
requirement of ensuring the time series data matches up with the correct
unique identifier. It has been identified that both physical and logical
unique identifiers can change, and so our TSDB will need to track
another unique identifier, there will need to be checks before inserting
data to link it with its time series unique identifier or generate a new
identifier.

##  

#### Time Series Databases \[13\]

The time series databases are represented by time series data, this is a
unique type of data that is characterised by each point being associated
with a time stamp or interval. As IoTa's data is generated by sensors
with time stamps, using a time series database is considered the best
option for handling such data.

It has many core benefits such as high performance, efficient data
storage, and powerful querying capabilities to help unlock meaning
behind large quantities of data.

Our chosen TSDB could be QuestDB, InfluxDB, Timescale, Prometheus, each
with different characteristics

QuestDB is a pure time series database (built from scratch), written
mostly in low-latency Java with some C++ and Rust. It is a fairly new
database but is highly ranked, through current tests it has implemented
well and fits criteria for being a top database contender for IoTa. Key
features include: supports Line Protocol, easy to use web console, high
performance, ease of use, excellent documentation. Thus far, the only
downside is there is no integrated compression.

TimescaleDB is built atop of postgres, it is considered to be a rather
popular database and key features include: excellent compression, good
performance, good scalability, uses SQL type language. Timescale appears
to be an excellent choice and rivals QuestDB whilst also including
compression. Thus far, the downside is that there is no integrated web
console.

InfluxDB is another built from scratch TSDB and is considered to be the
most popular implementation, it includes a comprehensive (and very
complex) web console, token based authentication, GZip compression, its
own query language and excellent performance. Thus far, key downsides
include difficulty of use and poor documentation.

PrometheusDB is another widely popular TSDB, for this to be implemented,
the above processes would be changed significantly, and for this reason
Prometheus is considered the worst choice, for implementation, it would
receive the message directly from the RabbitMQ exchange without a
process handling the processing.

#### APIs \[14\]

In addition to the above mentioned processes, we will be implementing an
API to interact with the chosen TSDB.

TSDB API : will sit as a container inside the existing docker compose
stack, it will allow a user to interact with the TSDB in order to pull
out time series data. It will fulfill one of the functional
requirements. Much like the existing API, we will choose FASTAPI for the
implementation library, and the API will be accessed primarily via the
CLI.

#### PosgresDB \[14\]

BACKUP POSTGRES : In order to fulfill the requirement of handling backed
up data, we will implement a script that will spin up a second postgres
container, along with a decoder and an existing time series queue, these
will only run if data is found inside a database backup folder. This
will allow us to run existing data into TSDB without reprocessing it
through the rest of the system.

The existing Postgres db will remain untouched

#### Service Communication \[14\]

logical_timeseries : we will subscribe to the existing
logical_timeseries (lts) exchange to receive incoming messages into
IoTaDecoder process

existing_timeseries : For now this feature has been tabled, if it does
get implemented (pending DPI team), very likely it will simply receive
input from existing mapper or similar.

This will be a temporary exchange/queue where data can be processed from
the backup postgres process if it is required.

## Key abstractions \[15\]

-   Time-series databases are databases which take in a continuous stream of time-stamped data, such as from a sensor. In this instance, the two time-series databases to be implemented for the IoTa platform should accept data from a variety of sources and amalgamate it into one

-   Exchanges allow multiple processes to subscribe in order to receive and process messages, this is how intercommunication is achieved in IoTa (via RabbitMQ)

-   A Process is designed to do a single task, i.e Device/Logical mapper is to map a physical device to a logical device, IoTa decoder is to convert IoTa message one that can be received by the TSDB

-   Docker compose / docker / stack all reference the underlying containerisation of IoTa. Each process, most of which are .py files, are running as a separate container inside a single docker compose stack, these can ultimately be thought of as files in a fresh directory, not linked to the underlying host environment.

-   TSDB API refers to a CLI ability to request data from the running TSDB, it will allow a user to type a command in order to request specific time series data between dates or possibly even for a device.

-   physical is linked to a physical unique device, whereas logical devices are created to ensure the data supply remains logical. If there is a physical pool-sensor-1, it might be linked to logical pool-A-sensor, if the physical sensor is replaced for any number of reasons, we'd still like pool-A-sensor to remain unchanged so that the data flow remains the same.

# 

#  

## Layers or architectural framework \[16\]

See figure in 9.0 for a breakdown of the processes.

There are three distinct patterns for the project and the existing IoTa
project, these are using a microservice architecture, publish/subscribe
pattern and a layered narrow waist design.

**<u>Microservice:</u>**

Each requirement is broken up into a single service (mostly python
script) running inside a docker compose stack. Where possible, the
services share a python image, however some services such as RabbitMQ or
TSDB require a full new image.

Each service should only be responsible for a single task, per above
(6.x). Our implemented features will follow this architecture principle
by ensuring a single task to be performed by each process we implement.

View of running containers (test environment, nginx is optional, only
CCRD is implemented)

![](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/docs/media/container_view.png?raw=true)

**<u>Publish/Subscribe:</u>**

In order to communicate between the services, IoTa uses RabbitMQ as a
message broker, our additions will follow this pattern.

There are currently three main exchanges in IoTa, they are:
physical_timeseries, logical_timeseries and ttn_raw. In our case, we
only need to concern ourselves with logical time series as this holds
the physical time series data but also has a linked logical device.

We will also implement a fourth exchange, existing_timeseries, that is
designed to handle existing messages from Postgres DB allowing them to
be partially reprocessed and added to TSDB.

With the exchanges, each message can be consumed by multiple processes,
and so adding an extra receiver to logical_timeseries will not affect
the existing listeners.

**<u>Narrow Waist:</u>**

There are multiple and varied sources of the data to the IoTa platform,
and this means that the message format received varies. At the front-end
of IoTa, the receivers will either decode or pass along to another
front-end process to standardise the message format that IoTa uses
internally.

This ensures that everything within the IoTa mid-processes receive and
handle the same data, allowing for easy addition of processes and
functions.

A typical message looks like this:

> *{*
>
> *\"broker_correlation_id\": \"83d04e6f-db16-4280-8337-53f11b2335c6\",*
>
> *\"p_uid\": 301,*
>
> *\"l_uid\": 276,*
>
> *\"timestamp\": \"2023-01-30T06:21:56Z\",*
>
> *\"timeseries\": \[*
>
> *{*
>
> *\"name\": \"battery (v)\",*
>
> *\"value\": 4.16008997*
>
> *},*
>
> *{*
>
> *\"name\": \"pulse_count\",*
>
> *\"value\": 1*
>
> *},*
>
> *{*
>
> *\"name\": \"1_Temperature\",*
>
> *\"value\": 21.60000038*
>
> *}*
>
> *\]*
>
> *}*

Where a *broker_correlation_id* can be used to track a time series point
to the sensor, a physical and logical unique identifier, a timestamp and
the time series data.

## Architectural views \[17, 17A\]

<u>**Component View:**</u>

<u>Red indicates new processes, whilst black is for existing.</u>

![](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/docs/media/component_diagram.png?raw=true)

**<u>Sequence Diagram:</u>** Receive Message

![](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/docs/media/seq_diagram.png?raw=true)
**<u>TSDB API Flow Chart:</u>**

![](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/docs/media/api_view.png?raw=true)
#  

##  Changelog

|Change ID|Existing Section|Change|Reason|
|--|--|--|--|
|--|Blue help text|removed|it is template text only
|1,2,3,4|2.X sections, reworked some paragraphs, added or removed others.|added challenges IoTa solves|Better narrowed it to our project not DPI as a whole, added extra information to better explain the constraints
|5|3.1 Assumptions|Added extra assumptions|Further details on the assumptions.
|6|3.2 Dependencies|Changed dependences|More narrow scoped dependencies
|7|4.0|Reworked section to be more focused on our changes rather than existing IoTa application|Narrowed scope to our project rather than IoTa project
|8|5.0|Reworked section to be more focused on our changes rather than existing IoTa application|Narrowed scope to our project rather than IoTa project
|9|6.0|New sentence to reiterate the architecture mechanisms|Expanded details for project
|10,11,12|6.1, 6.2, 6.3|Reworked sections to better highlight the new and old processes, and how they fit together|Narrowed scope to our project and expanded on details
|13|6.4|Added more info about TSDB, why it is important and outlined some of the key points for our prospective TSDB|More information about TSDB and the potential choices we have on offer through this project.
|14|6.5, 6.6, 6.7|Added section for API as it is not really clear which process tier it falls under,|Added postgres and exchanges sections|IoTa documentation does not include the RESTAPI into the process tiers and it is kind of separate to them, so I have done the same here.
|15|7.0|Added extra key abstractions to help clarify some of the key points|Added a little more detail to help show the full picture of the proposed system
|16|8.0|Completed layers section, this was not completed due to lack of understanding of whole project at earlier time, we have now a complete understanding of the architecture so able to complete this section|Able to now complete the section.
|17|9.0|Reworked existing diagram, added a few more|Better shows system
|17A|3.1, 4.0, 6.X, 9.0|Reworked component diagram after meeting with DPI, changed various sections in 6.0 to reflect the changes in component diagram.Fixed API flowchart having 2x No on a decision.|Removed or reworded information about caring about both physical and logical, we really only care about logical exchange.|highlighted features that are currently removed, however there is room that they may be implemented in some fashion.|This is all from a meeting with DPI.

