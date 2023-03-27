| DPI: IoTa Time-series Database | | 
| -- | -- |
| Supporting Requirements Specification | Date: <19/03/23> |
#
# 1. Introduction

The scope of the system entails the following:

-   To develop a service that handles messages sent from another program, then stores them in a specific format for later use.
    
-   Identify and implement a time-series database that will be utilized by the service to store data.
    
-   Implement an API to allow for specific requests to be fulfilled in regards to retrieval of data from the time-series database.
    
-   Allow for direct interaction with the database through command-line requests allowing for backup/restore
    
#
# 2. System-Wide Functional Requirements
    

-   The system must be able to translate data from the old FDT database into the new time-series database.
    
-   The system is required to retrieve messages from a copy of a table in the IoTa database, convert the messages to IoTa's internal message format, and then store them in the time-series database.
    
-   Data points extracted from new messages received by IoTa must be written to the time-series database.
    
-   The system requires an API that can be used to pull data for multiple devices between two timestamps.
    
#
# 3. System Qualities
### 3.1 Usability
-   Functionality to read from old message tables should be runnable via the command line.
    
-   The API should allow for simple queries to pull data from the time-series database.
    

### 3.2 Reliability
-   The system should confirm data is stored correctly in the database in case of errors.
    
-   The system must include backup and restore scripts for the time-series data.
    
-   The API should always be able to query the database during runtime.
    
### 3.3 Performance
-   The time-series database, and service should both startup with IoTa being run, through use of containers.
    
-   The output service may need to handle multiple messages at one time to be stored in the time-series DB.
    
-   The API will only need to manage individual requests at one time.
 
### 3.4 Supportability
-   The output service and time-series database must run within containers.
    
-   Output service must interpret messages received from RabbitMQ.
    
-   The time-series database must not require cloud hosting.
    
-   Images used must support being added to the Docker compose stack.
    
#
# 4. System Interfaces
### 4.1 User Interfaces
##### 4.1.1 Look & Feel
-   The API simply needs to accept queries based on the IoTa’s interface, and will also accept command line requests to run certain scripts.
    
-   Degree of user interaction will be limited due to the nature of the service.
  
##### 4.1.2 Layout and Navigation Requirements

-   Not applicable to the current scope, as no UI is required to be designed.
    

##### 4.1.3 Consistency
    

-   Will use the existing web interface, will otherwise provide command line responses with important information on execution.
    

##### 4.1.4 User Personalization & Customization Requirements
-   System is designed to be accessed through API and command-line, no UI additions at this point.

### 4.2 Interfaces to External Systems or Devices
##### 4.2.1 Software Interfaces
-   Must interface with RabbitMQ messages, and rebuild them for the time-series database.
    
-   Will interact with IoTa’s interface based on requests through use of the API to be developed.
    

##### 4.2.2 Hardware Interfaces
-   Should not be of concern, will be designed to run in a Docker container image, thus will execute on DPI’s hardware.
    

##### 4.2.3 Communications Interfaces
-   Will not directly interface with communication devices, messages are received from RabbitMQ software running in the Docker compose stack.  
    
#
# 5. Business Rules
### 5.1 Output Service Data Rules:
##### 5.1.1 Output service receives a message.
If the output service receives a message from RabbitMQ, then the service should extract the data points and store them in the time-series database.

##### 5.1.2 User request for FDT data transform
If the output service receives a request to transform data containing a copy of a table from the FDT database, the service should convert it into IoTa’s message format, and then save the data into the time-series database.

##### 5.1.3 User request for IoTa data transform
If the output service receives a request to transform data containing a copy of a table from the old IoTa database, the service should convert it into IoTa’s message format, and then save the data into the time-series database.

### 5.2 API Handling Rules:
##### 5.2.1 Application request for data
If IoTa is interfacing with the output service and requests data regarding specific devices between two points in time, return the data in the format utilized by IoTa.

### 5.3 Time-series Database Rules:
##### 5.3.1 Time-series data backup
If a desired time passes, a condition is met, or a request is received, then the time-series database will save a backup of the stored data.
##### 5.3.2 Time-series data restore
If a request is made via an output service script (likely accessible via the API or command line) then provide the user with options for restore, and allow them to select the restore point.
#
# 6. System Constraints
-   System must be developed using Python.
    
-   The service must run in the Python image provided by DPI and used with Docker compose.
    
-   The time-series database must run in a container and not require cloud-hosting.
    
#
# 7. System Compliance
### 7.1 Licensing Requirements
-   Possible licensing limitations related to chosen Time-series DB. – Unknown at this time
    
### 7.2 Legal, Copyright, and Other Notices
-   No specific legal compliance has been given, as the project is mostly backend focused, and unrelated to possible unethical behavior outside of loss of important data.
    
### 7.3 Applicable Standards
-   The system must be able to meet the performance requirements set by the existing IoTa components. This includes both handling RabbitMQ messages, and also responding to queries when requested.
    
-   Python code should follow PEP8 style guidelines for uniformity, as is often standard practice.
    
#
# 8. System Documentation
-   Documentation in this case could involve details on its implementation and how it links with other modules/containers within IoTa. This could include a form of architectural diagram based on the existing one for IoTa.
    
-   User/developer manual on how to interact with the service, through both explaining capabilities within the API, and also commands that can be used within a CLI.
    
-   Potentially include command for help within CLI if it becomes necessary, but functionality here should be simple.

