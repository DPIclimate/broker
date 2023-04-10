

|ITC303| |
| :- | :- |
|Project Plan Initiation Phase|`  `Date: 10/04/2023|

**ITC 303**

**Project Plan Initiation Phase**

# 1. **Introduction**
This Project Plan details the major tasks that are to be accomplished within the one year of the DPI: IoTa Timeseries Project. This covers the four phases of the project, which include: the Inception phase, the Elaboration phase, the Construction phase and the Transition phase.

The Inception phase, which should be completed as of the publish date of this document, establishes timelines for important initial phase documents to be completed and knowledge to be gathered.

The Elaboration phase focuses on mitigating risks identified with the project, and to begin development of the project in a testing capacity. Since our project involves the deployment of a timeseries database, the majority of the elaboration phase will be spent dedicated to testing 4 separate open-source timeseries database offerings. This is conducted to establish development protocols and familiarity with all relevant solutions, and to present our findings with our sponsors.

Barring any major changes to the direction of the project, the 
# 2. **Project organization**
The project team consists of four members: Callum, Rishabh, Sara and Zac. 

As such, no specific work areas, domains or packages have been assigned to team members. Team members are all expected to contribute to the development and deployment of the project equally and in roughly the same capacity. 

A separate CSU team is also working with the Digital Agriculture team’s DPI projects. In a combined sponsor meeting, collaboration between the teams was proposed by the project sponsors. However, at the time of writing no such plans have materialized. It is expected that as the project progresses, there will be some need for inter-team communication between the two teams.

# 3. **Project practices and measurements** 
The overarching technical development strategy to be used over the course of this project is iterative development. As mentioned previously, this takes the form of 13 2-week iterations split across 4 phases, all focusing on progressive stages of the project. 

Progress in each iteration will be tracked against an official iteration plan document which is collectively made by the group at the start of the iteration. The goals of each iteration are to be dictated roughly by this document, which will cover the major goals for the lifetime of the project.

# 4. **Deployment**
As the substantive project is the deployment of a new timeseries database solution in the backend of the existing IoTa project, the deployment will be carried out across several stages. To ensure that the solution eventually chosen fulfils all the needs of the DPI team as far as features, compatibility and self-governance is concerned.

For this reason, during the elaboration and construction phases, the team will individually test and deploy 4 different timeseries database solutions. The solutions themselves have different feature sets, database functional modalities and compatibilities: the team will aim to find the balance of solutions which will suit the needs of the DPI team for all the mentioned.


# 5.  **Project milestones and objectives**


|**Subject**|**Phase**|**Iteration**|**Dates**|**Primary objectives** (risks and use case scenarios)|
| :- | :- | :- | :-: | :- |
|ITC303 – Software Development Project 1|Inception Phase|I-1|13/03 – 26/03|<p>Establish Vision</p><p>Establish Initial Use Case Model</p><p>Complete Preliminary Non-functional Requirement Analysis</p><p>Identify/Document Candidate Architectures</p><p>Establish Version Control Repository</p><p>Establish Shared Collaborative Document Repository</p>|
|||I-2|27/03 – 9/04|<p>Establish Risk List</p><p>Shortlist Final Candidates for Timeseries Database Solution</p><p>Complete Full Description for Critical Core Risky Difficult (CCRD) Use Case </p><p>Implement Technical Competency Demonstrator</p><p>Create Test Plan</p><p>Establish Initial Project Plan</p><p>Deliver Life Cycle Objectives Milestone (LCOM)</p><p>Complete Inception Phase Project Assessment</p>|
||Elaboration Phase|E-1|<p>10/04 – 23/04</p><p>(Session Break)</p>|<p>Gain knowledge and skills base for timeseries database specific work.</p><p>Implement Communication between RabbitMQ and SQL</p><p>Complete Development Testing for Communication framework</p>|
|||E-2|24/4 – 7/05|<p>Gain knowledge and skills base for docker and virtualisation-specific work</p><p>Implement link between timeseries database output and mid-tier processor input</p><p>Complete Development and Integration Testing for linking framework</p>|
|||E-3|8/05 – 21/05|<p>Implement link between mid-tier processor output and timeseries database input </p><p>Complete Development and Integration Testing for linking framework</p><p>Deploy Executable Architecture in Trial Environment</p><p>Complete Internal User Acceptance Testing for CCRD Use Case in Trial Environment</p>|
|||E-4|22/05 – 2/06|<p>Contingency</p><p>Deliver Life Cycle Architecture Milestone (LCAM)</p><p>Complete Elaboration Phase Project Assessment</p>|
|Mid-year Semester Break| | | | |
|ITC309 – Software Development Project 2|Construction Phase|C-1|10/07 – 23/07|<p>Implement Timeseries Database Solution 1 (InfluxDB) for all Use Cases</p><p>Complete Development and Integration Testing for 2nd Highest Priority Use Case(s)</p><p>Complete Internal User Acceptance Testing for 2nd Highest Priority Use Case(s)</p>|
|||C-2|24/07 – 6/08|<p>Implement Timeseries Database Solution 2 (Timescale) for all Use Cases</p><p>Complete Development and Integration Testing for 3rd Highest Priority Use Case(s)</p><p>Complete Internal User Acceptance Testing for 3rd Highest Priority Use Case(s)</p>|
|||C-3|7/0 – 20/08|<p>Implement Timeseries Database Solution 3 (QuestDB) for all Use Cases</p><p>Complete Development and Integration Testing for 4th Highest Priority Use Case(s)</p><p>Complete Internal User Acceptance Testing for 4th Highest Priority Use Case(s)</p>|
|||C-4 |<p>21/08 – 3/09</p><p>(Session Break)</p>|<p>Implement Timeseries Database Solution 4 (Prometheus) for all Use Cases</p><p>Deliver Initial Operation Capability Milestone (IOCM)</p><p>Complete Construction Phase Project Assessment</p>|
||Transition Phase|T-1|4/09 – 17/09|<p>Deploy Chosen Timeseries DB in Trial Environment</p><p>Ensure all connections are compatibilities are maintained </p><p>Complete 1st Round External User Acceptance Testing</p><p>Resolve Any Identified Issues</p>|
|||T-2|18/09 – 1/10|<p>Complete 2nd Round External User Acceptance Testing</p><p>Deploy Timeseries DB to production environment through logical pull request</p><p>Resolve Any Identified Issues</p>|
|||T-3|2/10 – 13/10|<p>Contingency</p><p>Resolve pull request issues with master branch of DPI</p><p>Deliver Product Release Milestone (PRM)</p><p>Complete Final Project Assessment</p>|




