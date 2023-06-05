|**DPI: IoTa Time-series Database** | |
| :- | :- |
|Supporting Requirements Specification|`  `Date:  <19/03/23>|


**DPI: IoTa Time-series Database**

**Supporting Requirements Specification**
1. # <a name="_heading=h.gjdgxs"></a>**Introduction**
The scope of the system entails the following:

- To develop a service that handles messages sent from another program, then stores them in a specific format for later use.
- Identify and implement a suitable time-series database that will efficiently store and manage the data.
- Implement a robust and user-friendly API to facilitate seamless retrieval of data from the time-series database.
- Allow for direct interaction with the database through command-line requests allowing for backup/restore
1. # **System-Wide Functional Requirements**
- The system is required to retrieve messages from a copy of a table in the IoTa database, convert the messages to IoTa's internal message format, and then store them in the time-series database for future usage
- Data points extracted from new messages received by IoTa must be written to the time-series database to ensure information is always up-to-date.
- The system requires a comprehensive API that can handle requests to retrieve data for multiple devices within specified time intervals.
- Data will need to be visualised within the existing web application.
1. # **System Qualities**
   1. # **Usability**
- Functionality to read from old message tables should be accessible via the command line and API, allowing users to extract and process historical data efficiently.
- The API should provide a straightforward and intuitive interface for querying the time-series database, ensuring ease of use for users.
  1. # **Reliability**
- The system should perform thorough data validation to ensure accurate storage of information, preventing errors or inconsistencies.
- Implement backup and restore scripts for the time-series data to safeguard against data loss or system failures.
- The API should be designed to consistently query the database during runtime, ensuring uninterrupted access to data.
  1. # **Performance**
- The time-series database and service should seamlessly start up with IoTa being run, leveraging containerisation for efficient deployment.
- The output service should efficiently handle multiple messages simultaneously, ensuring optimal performance when storing data in the time-series database.
- The API will handle individual requests, focusing on providing efficient retrieval of data from the time-series database.
  1. # **Supportability**
- Both the output service and time-series database must run within containers, ensuring portability and ease of deployment.
- The output service should be capable of interpreting messages received from RabbitMQ, facilitating seamless integration.
- The time-series database should be deployable without requiring cloud hosting, providing flexibility in infrastructure choices.
- Images used should be compatible with the Docker compose stack, ensuring smooth integration with the existing environment.
1. # **System Interfaces**
   1. # <a name="_heading=h.30j0zll"></a>**User Interfaces**
      1. # *Look & Feel* 
- The API simply needs to accept queries based on the IoTa’s interface, and will also accept command line requests to run certain scripts.
- Degree of user interaction will be limited due to the nature of the service.
- Visual representation of data will be required, likely in the form of a graph.
  1. # *Layout and Navigation Requirements*
- Visualisation of data will be accessible within the existing web application, likely under each logical device
  1. # *Consistency*
- Will use the existing web interface, will otherwise provide command line responses with important information on execution. 
  1. # *User Personalization & Customization Requirements*
- System is designed to be accessed through API, command-line, and the existing web application.
  1. # <a name="_heading=h.1fob9te"></a>**Interfaces to External Systems or Devices**
     1. # *Software Interfaces*
- Must interface with RabbitMQ messages, provide the necessary transformations and rebuild them for the time-series database.
- Will interact with IoTa’s web application based on requests for visualisation of data through use of the API to be developed.
  1. # <a name="_heading=h.3znysh7"></a>*Hardware Interfaces*
- The system will be designed to run in a Docker container image, and therefore will be extensible and movable, compatible with DPI’s hardware.
  1. # <a name="_heading=h.2et92p0"></a>*Communications Interfaces*
- Will not directly interface with communication devices, messages are received from RabbitMQ software running in the Docker compose stack. 


|Confidential|© Team 3, 2023|Page |
| :- | :-: | -: |

1. # **Business Rules**
   1. # **Output Service Data Rules:**
      1. # *Output service receives a message.*
If the output service receives a message from RabbitMQ, then the service should extract the data points and store them in the time-series database.

1. # *User request for IoTa data transform*
If the output service receives a request to transform data containing a copy of a table from the existing IoTa database, the service should convert it into IoTa’s message format, and then save the data into the time-series database.
1. # **API Handling Rules:**
   1. # *Application request for data*
If IoTa is interfacing with the output service and requests data regarding specific devices between two points in time, the system should retrieve and return the requested data in the format utilised by IoTa, ensuring compatibility.
1. # **Time-series Database Rules:**
   1. # *Time-series data backup*
If a desired time passes, a condition is met, or a request is received, then the time-series database will save a backup of the stored data.
1. # *Time-series data restore*
<a name="_heading=h.tyjcwt"></a>In the event of a data loss or user request, the output service script (accessible via the API or command line) should provide users with options for restoring data, allowing them to select the desired restore point.
1. # <a name="_heading=h.ro56j0q8jgyg"></a>**Web Application Rules:**
   - # <a name="_heading=h.yc37u0moec3q"></a>*5.4.3	Aggregate time-series data for visualisation*
For the purposes of analysis, the web application in conjunction with the API will have the ability to display data visually.
1. # **System Constraints**
- The system must not be developed in a language other than Python.
- The service must be able to be run in the Python image provided by DPI and used with Docker compose.
- The time-series database must run in a container and not require cloud-hosting.
1. # **System Compliance**
   1. # <a name="_heading=h.3dy6vkm"></a>**Licensing Requirements**
- <a name="_heading=h.1t3h5sf"></a>Possible licensing limitations related to chosen Time-series DB. 
- Note: all database solutions considered are open-source databases, with the slight exception of InfluxDB which has both an open-source and proprietary offering.

1. # **Legal, Copyright, and Other Notices**
- No specific legal compliance has been given, as the project is mostly backend focused, and unrelated to possible unethical behaviour outside of loss of important data.
  1. # <a name="_heading=h.4d34og8"></a>**Applicable Standards**
- The system must be able to meet the performance requirements set by the existing IoTa components. This includes both handling RabbitMQ messages, and also responding to queries when requested.
- Python code should follow PEP8 style guidelines for uniformity, as is often standard practice.
1. # **System Documentation**
- <a name="_heading=h.2s8eyo1"></a>Documentation to involve details on its implementation and links with other modules/containers within IoTa. Aim to include a form of architectural diagram based on the existing one for IoTa.
- User/developer manual on how to interact with the service, through both explaining capabilities within the API, and commands that can be used within a CLI.
- Include a command for help within CLI if it becomes necessary, but functionality here should be simple.

1. # <a name="_heading=h.3w54kekzn2zu"></a>**CCRD**
- The CCRD has been chosen due to it being the most used feature and easiest to fail, along with it being the main feature that the project cannot do without.
- There are two main use cases for the CCRD:
  - 1. A valid message is received by IoTa and passed onto our decoder, message is parsed and the time series data is inserted into our implemented TSDB for later use.
  - 2. An invalid message is passed onto our decoder, the message is attempted to be parsed and ultimately rejected. Invalid messages are likely due to incomplete data, or incorrect formatting of IoTa internal formatted messages.
    - Like the existing IoTa processes, if an invalid message is received, we will simply drop it, an ack response will be used to signify the acceptance or rejection of a message.
- Functional requirements of CCRD:
  - Parse incoming message and if it is a valid message, insert it into TSDB, send ack response.
  - Data is not modified beyond necessary, i.e timestamps likely need to be converted, however measurements should not be rounded etc.
  - Handle errors and invalid messages correctly such that the system can continue to accept incoming messages.
- Non functional requirements of CCRD:
  - Ensure reliability - auto restart the process in case of failure, adequate responses.
  - Ensure usability - the process should be autonomous when starting the rest of the application.
  - Ensure performance - processing and/or inserting data for or into TSDB should be in the milliseconds per message.
  - Ensure scalability - IoT sensors will increase overtime, processes must be able to handle a higher rate of data input than it currently requires.
  - Ensure capacity - storage requirements are important as data is stored for long periods of time with constant stream of messages 24/7.



**Use Case Diagram**

![](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/docs/media/ccrd_use_case.png?raw=true)

**Change Log**


|**Section**|**Change Made**|**Reason**|
| :-: | :-: | :-: |
|1\. Introduction|Added a brief overview of project significance and removed reference to FDT data import|To provide context and highlight benefits|
|2\. System-Wide Functional Requirements|Clarified data format translation from FDT DB|To ensure seamless migration of historical data|
|3\.1 System Qualities - Usability|Added clarification on error handling|To assist users in case of issues|
|3\.2 System Qualities - Reliability|Added mention of data consistency mechanisms|To ensure accurate and reliable data storage|
|3\.3 System Qualities - Performance|Emphasised the use of containerisation|To emphasise the goal of efficient deployment and scalability|
|4\.1 User Interfaces|Added reference to data visualisation and creating UI|Stretch goal for web application was decided to be included|
|4\.2.1 System Interfaces - Software Interfaces|Clarified data transformation process and|To ensure proper integration with RabbitMQ |
|4\.2.2 System Interfaces - Hardware Interfaces|Highlighted Docker container usage|To ensure hardware compatibility|
|5\.2 Business Rules - API Handling Rules|Fixed wording by adding clarification on data retrieval format|To ensure compatibility with IoTa interface|
|5\.3 Business Rules - Time-series Database Rules|Added mention of data protection|To ensure data resilience and safety|
|5\.4 Business Rules - Web Application Rules|Added section with business rule for web application stretch goal|Stretch goal for web application was decided to be included|
|6\. System Constraints|Clarified Python usage and containerisation|To ensure consistency and portability and ensure that PromDB doesn’t break the requirements|
|7\. System Compliance|Added information about licensing requirements|To address potential legal considerations|
|8\. System Documentation|Changed wording by removing low modality conditional words|To provide a comprehensive understanding|
|9\. CCRD|Added section to describe CCRD and alt flows.|Per marking matrix|
