## Technical Competency Plan

#### ***<u>Document Summary</u>***

This document exists to summarise how Team 3 will show competency for our chosen project.

The goal of this plan is to be able to show competency through a simple implementation of our working stack verified by tests.

We will target a few key use cases to implement in a proof of concept style application.

#### ***<u>Target Platform & Key Technologies</u>***

To show competency for the project we must mirror the project technology stack.

The below table will highlight what technologies we'll be using.

As our chosen project is to in a simple sense, receive messages from RabbitMQ and then send this to a Time Series Database, as well as pull data from the Time Series Database through CLI API, we will target these use cases.


|Area|Technology|
|--|--|
|Environment|Linux|
|Container|Docker|
|Language|Python, Bash|
|Testing|pytest|
|Database|QuestDB^|
|Version Control|git|
|Libs/3rd Party|RabbitMQ, FastAPI|

#### ***<u>Key Notes</u>***
- The docker containers used will not be identical to the project, they will be basic implementation to show that docker can be used.
- ^The TSDB we use for proof of competency may not be the TSDB that we will ultimately choose as we will be evaluating multiple TSDB's in the later stages of the project, and as such showing ability to use a single TSDB should be sufficient.
- The program will not be fluid, it will be designed to complete the tests that will evaluate if the key use cases chosen to show competency have succeeded.
- The use cases, if you'd call them that, shown do not fully reflect the actual use cases of the project, instead they are to show competency of a basic version of that use case through input/output/processing via the specified technologies.
- Certain aspects such as containers will not be tested as such level of testing would be out of scope for this proof of competency and if these aspects fail then the tests will also fail
- The data types and message formats do not reflect the ones that will be used in real project.
- Ideally each person to implement a single use case - taken via Trello
- Some extra libraries may be linked however these are not constrained by the project as much as the listed ones
- Some of the bash scripts does not hide or do logic well, and so it will just try stop/remove a container regardless if it exists and will almost always show an error, however the error is safe to ignore.

#### ***<u>Use Cases to be Implemented</u>***

During our correspondence with stakeholders, one use case was removed from project so it has been subsequently removed from here, the use cases seem short however, they run in the technology stack we're using.

There are 7 tests generated to show the use cases working as intended.

|id|use description|input|output|
|--|--|--|--|
|0|Send message from RabbitMQ to python|JSON Object|JSON Object|
|1|Store message from RabbitMQ by python to QuestDB|JSON Object|
|2|Retrieve data from QuestDB via CLI API|CLI Command|JSON Object|

#### <u>***Implementation***</u>

We have multiple docker containers:
- RabbitMQ to handle messages - this is a base image direct from docker
- QuestDB for a database - this is a base image direct from docker
- FastAPI for api implementation (via Uvicorn) - this is build per our own Dockerfile

Pytest is run outside of the containers, it was originally going to be run inside the container, however it made more sense to have it outside the containers.

These are started with:
```./start.sh```
- This one will start our containers, and build/start our api too

Then we can run our tests via:
```./test.sh```
- This will call pytest to run tests, but also figure out the IPAddresses for each docker container and send it to pytest, this is required as some of the containers talk to another and require the IP.

And finally stop the containers via:
```./stop.sh```
- This will simply call stop for the containers.
