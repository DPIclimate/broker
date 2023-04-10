# Inception Phase Status Assessment
## 1. Assessment against Objectives of the Inception Phase 
### 1.1 Do we know what we are trying to achieve?
The aim of the project is to simplify the system by using a TSDB, move from a cloud based database to hosting inhouse, allow previous messages used by both IoTa and FDT to be converted and stored in the new TSDB, and include an API to query and retrieve data.﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿ This is embodied in the completed Vision Document.
We understand the main functional requirements of the project which are:
- Be able to translate data from the old FDT database into the new TSDB
- Retrieve messages from a copy of a table in the IoTa DB, convert to IoTa’s internal message format, and store in the TSDB
- Write new messages received by IoTa into the TSDB
- API to query data for multiple devices between two timestamps

This is shown in the completed Functional Requirement model embodied in completed Supporting Requirements Specification Document.

We understand the main Non-Functional requirements of the project which are:
- Usability
  - Easy to use, integrates previous systems
- Reliability
  - Backups, low downtime, data confirmation
- Performance
  - DB to handle multiple records at once, API one request at a time, Scalability: to handle data from many devices over a long period of time
- Supportability
  - Runs within containers added to existing Docker Compose stack
  - Works with previous system messages
 
This is shown in the completed Non-Functional Requirement model embodied in completed Supporting Requirements Specification Document.

### 1.2 Do we know how we are going to achieve it?
We have a good idea of how we are going to achieve our aims. We are going to choose and implement a time series database. This is shown in the completed Architecture Notebook.
We have a good understanding of the project specific risks facing our project and how we are going to deal with them. The risks are:
- Skills and Knowledge
- Selecting suitable TSDB
- Remote team with loose bindings
- Message Parsing
- Microservice Architecture
- Uncertainty of scope
- Project Complexity

Our evolving understanding of risks is shown in the ongoing risk list and discussed further below in Section 4.

We have a good understanding of how we are going to check that our application delivers the intended functionality and system properties. Our key areas of concern and the test strategies we will use to address these concerns are as follows:
- Performance - ensure the service can handle multiple messages and save them to the TSDB
- Compatibility -  Ensure TSDB works within the Docker compose environment, ensure the web interface is providing the API with sufficient detail for different methods
- Integrity - Ensure the desired details are retrieved from messages sent to the API and also IoTa DB CLI prompts
- Connectivity - Ensure there are no issues in service that may result in dropped connections between container elements
- Interfacing - Test communication from API to service, to ensure all method calls perform correctly

This is shown in the completed Master Test Plan.

We have a good understanding of the dependencies and likely completion times for different parts of the project. Target completion dates for key aspects of the project are as follows:
- 21/05/2023 - Deploy Executable Architecture in Trial Environment
- 02/06/2023 - Deliver Life Cycle Architecture Milestone
- 17/09/2023 - Deploy Chosen TSDB in Trial Environment
- 01/10/2023 - Production Environment pull request 
- 13/10/2023 - Resolve all pull request issues

This is shown in the Initial Project Plan.

### 1.3 Skills required
Our project requires skills using the following key tools and technologies:
- Docker Compose
- Python
- REST API
- Time Series database of our choosing

We have demonstrated that we have the skills to use these technologies through the implementation of a technology competency demonstrator.


## 2. Deliverables
### 2.1 Project Vision
- This document addresses the core idea and business case for the project.
- No issues.
### 2.2 Supporting Requirements Specification
- This document addresses the functional and non-functional requirements.
- Some issues with scope to be clarified with project sponsor DPI, some changes have already been made to requirements since project inception.
### 2.3 Architecture Notebook
- This document covers the current architecture utilised by DPI that the project will have to integrate with. It also addresses achieving the functional and non-functional requirements set out in above documents. 
- No issues.
### 2.4 Risk List
- This document covers project specific risks and mitigation strategies for each, as well as triggers and symptoms for each, including a contingency plan for worst case scenario.
- No issues.
### 2.5 Master Test Plan
- This document addresses testing aims and use cases for the project to ensure requirements are met and the project meets its goals.
- Some issues were encountered isolating risks relevant to the test plan.
### 2.6 Initial Project Plan
- This document covers project timeline and iteration schedule, including specific delivery dates for select artefacts or documents. 
- No issues.
### 2.7 Technical Competency Demonstrator
- This document addresses the technical skills required for this project, and either displays competency or a plan to achieve competency.
- No issues.
### 2.8 Inception Phase Status Assessment
- This document is the current document, and addresses the project overall and gives a view of progress against Inception Phase aims.
- Minor issues based on dependencies to other documents, easily resolved on completion of other documents.


## 3. General Issues
Thus far there have been no key issues that would impact the project outside of those outlined in the risk list document.
The closest issue was poor communication through the early stages, however this has been addressed through discord updates, trello framework and shared google docs.


## 4. Risks
### 4.1 Skills and Knowledge
- Team skills and knowledge required for this project are being developed alongside the project. 
- Mitigation strategy is to enforce required learning as work items during iterations, assign buddy/mentor roles based on strengths to facilitate learning and work item completion to high standards.
- This risk is ongoing but manageable.
### 4.2 Selecting Suitable TSDB
- Selection of a suitable TSDB is crucial to the success of the project. Selecting an unsuitable one puts the whole project at risk. Improperly implementing a suitable one puts Functional and Non-Functional requirements at risk.
- Mitigation is in analysis of TSDB design and extensive research/testing of available options.
- This risk is ongoing but manageable.
### 4.3 Remote Team with Loose Bindings
- Team members are all remote, have never met, and are not bound by contract/employment. 
- Mitigation is to enforce mutually agreed team charter, as well as to be proactive in communication within the team.
- This risk is ongoing but manageable.
### 4.4 Message Parsing
- A key functional requirement is to parse incoming messages or messages from prior databases. 
- Mitigation is to ensure more time is spent to ensure incoming and outgoing messaging requirements are met, and to alter implementation of message parsing if required. 
- This risk is closed - after communicating with stakeholders, this key FR has been cancelled so now we just need to parse messages straight into TSDB
### 4.5 Microservice Architecture
- The current architecture for the platform uses microservices, the project will need to integrate well with existing services which may increase the chance of errors and pain points.
- Mitigation is to rethink the design to ensure the integration is suitable with existing systems, and to complete extensive unit testing to catch errors early.
- This risk is ongoing.
### 4.6 Uncertainty of Scope
- Project scope remains a little unclear, with conflicting or missing information around project details. 
- Mitigation is to form a strong communicative relationship with the project sponsor, and meet often to address issues as they arise. 
- This risk is closed - We’ve addressed this by communicating with stakeholders and now have a rather clear understanding of the project and scope, this risk is no longer considered a risk.
### 4.7 Project Complexity
- Project requires integration between multiple database technologies, existing and new, as well as working with/around multiple message formats, multiple devices, and third party platforms/technologies.
- Mitigation is to ensure time is well spent determining the correct TSDB before implementation begins and thorough testing.
- This risk is closed - the complexity of the project is now considered a non issue now that we’ve got a better grasp of the FR/NFRs


## 5 Summary – Overall Project Progress
The aims of the Inception Phase have been well met, with the project making adequate progress through them. The Project Vision outlines what the project aims to achieve, and why these aims are required. The how of completing a successful project is outlined across the Architecture Notebook, Supporting Requirements Specification, Master Test Plan, and Project Plan. Required skills and competencies are demonstrated in the Technical Competency Demonstrator.

At present, there are no on-going issues. Any issues so far have been resolved. 

Some of the identified risks have been resolved, and the remaining risks that are on-going are all being monitored to ensure they remain manageable.

