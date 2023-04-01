## Technical Competency Plan

***<u>Document Summary</u>***

This document exists to summarise how Team 3 will show competency.

The goal of this plan is to be able to show competency through a simple application verified by a set of tests.

We will target a few key use cases to implement in a proof of concept style application.

***<u>Target Platform & Key Technologies</u>***

To show competency for the project we must mirror the project technology stack.

The below table will highlight what technologies we'll be using.

|Area|Technology|
|--|--|
|Environment|Linux|
|Container|Docker, Docker Compose|
|Language|Python, Bash|
|Testing|pytest|
|Database|QuestDB^|
|Version Control|git|
|Libs/3rd Party|RabbitMQ, FastAPI|

***<u>Key Notes</u>***
- The docker containers used will not be identical to the project, they will be basic implementation to show that docker can be used.
- ^The TSDB we use for proof of competency may not be the TSDB that we will ultimately choose as we will be evaluating multiple TSDB's in the later stages of the project, and as such showing ability to use a single TSDB should be sufficient.
- The program will not be fluid, it will be designed to complete the tests that will evaluate if the key use cases chosen to show competency have succeeded.
- The use cases, if you'd call them that, shown do not fully reflect the actual use cases of the project, instead they are to show competency of a basic version of that use case through input/output/processing via the specified technologies.
- Certain aspects such as containers will not be tested as such level of testing would be out of scope for this proof of competency and if these aspects fail then the tests will also fail
- The data types and message formats do not reflect the ones that will be used in real project.
- Ideally each person to implement a single use case - taken via Trello
- Some extra libraries may be linked however these are not constrained by the project as much as the listed ones

***<u>Use Cases to be Implemented</u>***
|id|use description|input|output|
|--|--|--|--|
|0|Send message from RabbitMQ to python|JSON Object|JSON Object|
|1|Process a message by converting it to another format|JSON Object|CSV|
|2|Store message 'processed' by python to QuestDB|JSON Object|ack|
|3|Retrieve data from QuestDB via CLI API|CLI Command|JSON Object|
