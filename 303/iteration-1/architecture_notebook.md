# DPI: IoTa Timeseries Database Architecture Notebook

## 1. Purpose
This document describes the philosophy, decisions, constraints, justifications, significant elements, and any other overarching aspects of the system that shape the design and implementation of the Time Series Database for the NSW Department of Planning and Industry’s IoTa project. 

## 2. Architectural goals and philosophy

Formulate a set of goals that the architecture needs to meet in its structure and behavior. Identify critical issues that must be addressed by the architecture, such as: Are there hardware dependencies that should be isolated from the rest of the system? Does the system need to function efficiently under unusual conditions?]
The Department of Planning and Industry launched an “Climate Smart Pilots” project for the Digital Agriculture team, specifically to observe the impact of digital agriculture strategies on reducing climate change. The secondary goal of the project was to explore the current usages of agriculture technologies, and how they can be incorporated into existing Australian farming practices.

The project was started in 2018 and contains several pilot sites all over NSW. These sites contain various sensors: salinity, soil health, temperature, humidity, weather stations etc, which gather data from the sensors. This data is transmitted to a node through the LoRaWAN protocol to a gateway. This gateway then uses a separate framework called TTN to transmit the data over the internet to a database from where end-users can access this data.

The back-end framework for the project has been migrated once over the lifetime of the project from ThingSpeak to ThingsBoard. The migration was necessary as the scope of the project expanded from one datasource (LoRaWAN gateway) to several different data points. However, the transition was difficult and complicated, and the new (current) backend solution is not adequately fulfilling the needs of the project.

The main goal of the Time Series database team is to reduce dependency on third-party IoT time series database platforms, and to migrate the existing data collection system to a custom-built time series database solution hosted on the DPI network. By using a homegrown time series database solution, the team will be able to customise the feature-set of the database to integrate all the data in their expected format.

The design philosophy for this project is driven by key considerations owing to the complexity of the project’s existing architecture. The DPI Digital Agriculture team’s Climate Smart Pilots project is an ongoing project with a web of infrastructure already in place to retrieve and deploy sensor data. It is imperative that the new time series database backend is made compatible with the existing framework. This involves being able to accept time series data from a variety of data sources, and to have minimal downtime during deployment to not interfere with data collection.

In addition, a key consideration for the project is reliability of deployment. The sensors gather climate data continuously, and this data is fed into the database continuously. The database deployment must be robust with a 99.999% uptime. If possible, redundancies should also be incorporated into the architecture to reduce data loss in the event of catastrophic system failure. 

## 3. Assumptions and dependencies

### 3.1 Assumptions
The team either has the skills required or will be able to learn the skills required to develop and deploy a time series database solution.

Ben and David will be available to assist the team with any questions they have about the project, and to provide guidance on architectural requirements constraints and decisions

### 3.2 Dependencies 
- The existing architecture should be compatible with and supported by the new time series database. This involves the database accepting inputs from the following:
  - MQTT pollers,
  - REST API pollers
  - TTN decoders,

- The time series database should be able to write to existing backend structures which represent the data for the end-users, including:
  - Ubidots Writer
  - Other future planned destinations	

## 4. Architecturally significant requirements
The time series database must be able to support: 
- Multiple communications protocols including LoRaWAN via The Things Stack Community Edition, NB-IoT with MQTT, and polled sources via vendor APIs.
- Multiple message formats including base64 encoded binary, JSON, and CSV.
- The replacement of devices in the field, while requiring the data from that location to continue to be recorded in the same series of data in the time series database.
- Changes in IoT data storage and dashboardings platforms.
- The potential necessity for reprocessing messages due to bugs in the message decoders.
- Management and monitoring of the system at runtime.

Many of these requirements are fulfilled by the IoTa backend, which coordinates the messaging between the different data sources.   

## 5. Decisions, constraints, and justifications
- Ensure the TSDB framework selected is compatible with legacy inputs and outputs for TSDB that are currently in use. This is required to ensure compatibility with the existing infrastructure, and the LoRaWAN and MQTT input that the current system receives.
- Ensure the developer team is familiar with the database modality of the chosen TSDB framework. The developers must be able to replicate and enhance the functionality of the existing TSDB, and so must have a good grasp on the usage of the solution
- The TSDB framework chosen must allow for a self-hosted option. The Digital Agriculture team has indicated that for their next TSDB, they would prefer a custom-built self-hosted solution. TSDB offerings that exist solely on the cloud are not eligible.

## 6. Architectural Mechanisms

### 6.1 Front-End processors
The front-end processors are responsible for accepting or fetching messages from the various telemetry sources. Most sensors are connected to LoRaWAN nodes whose messages are received via the The Things Stack Community Edition. Growing number of YDOC NB-IoT nodes, and a few sensors whose telemetry must be retrieved via polling vendor REST APIs.

Each front-end processor is responsible for accepting or retrieving messages from its source and transforming those messages into IoTas own message format for use throughout the remaining processing stages, before publishing the messages to an exchange leading into the mid-tier narrow-waist processes.

Front-end processors are responsible for creating physical devices in the IoTas database. This must be done when a message from a new device is received. Each physical device has a map that can be used for storing free-form information against the device. 

Finally, front-end processors are responsible for generating and assigning the correlation id to each message as it is received and should record every message along with its correlation id in the raw_messages database table. This should be done as soon as possible so the message has the best chance of being stored somewhere before any errors cause the processor to abort processing that message.

### 6.2 Mid-Tier processor
There is currently one mid-tier processor, the logical mapper. The logical mapper's job is to determine where to send the telemetry received from a physical device. This decision is informed by a table in the database that maps a physical device to a logical device. This mapping must be updated when a physical device is replaced in the field so that data from the new device flows to the same destination.

The mapping is maintained manually using a CLI tool or the management web app, both of which provide a command to create a logical device based upon an existing physical device and then map the two. This is not done automatically because when a sensor is replaced in the field and a new physical device is created by a front-end processor, the telemetry from that new sensor/physical device should flow to the same logical device, not a new one.

### 6.3 Back-End processors
A back-end processor is responsible for writing time series data to destinations such as IoT platforms or locally hosted time series databases.

There are currently two back-end processors:

- delivery.UbidotsWriter writes to the current IoT platform, Ubidots.
- delivery.FRRED writes the messages to a file system directory defined by the DATABOLT_SHARED_DIR environment variable, where the Intersect DataBolt process is polling for them. For example, to write message files to the /home/abc/databolt/raw_data directory set DATABOLT_SHARED_DIR=/home/abc/databolt in the compose/.env file.

### 6.4 Role of Time Series Databases
The time series databases are represented by physical_timeseries and logical_timeseries in the below diagram. 
- physical_timeseries is responsible for connecting the data in the front-end (the sensors) to the mid-tier processor – the device mapper.
- logical_timeseries receives the data from the device mapper and sends it over to the back-end for end-user usage. The current back-end devices include: the Ubidots writer, and a separate raw-data directory.

## 7. Key abstractions
Time-series databases are databases which take in a continuous stream of time-stamped data, such as from a sensor. In this instance, the two time-series databases to be implemented for the IoTa platform should accept data from a variety of sources and amalgamate it into one 

## 8. Layers or architectural framework

NA - more project progression required to fill this section out of the architecture plan. 

## 9. Architectural views

See attached file.

Recommended views
Logical: Describes the structure and behavior of architecturally significant portions of the system. This might include the package structure, critical interfaces, important classes and subsystems, and the relationships between these elements. It also includes physical and logical views of persistent data, if persistence will be built into the system. This is a documented subset of the design.
Operational: Describes the physical nodes of the system and the processes, threads, and components that run on those physical nodes. This view isn’t necessary if the system runs in a single process and thread.
Use case: A list or diagram of the use cases that contain architecturally significant requirements.

