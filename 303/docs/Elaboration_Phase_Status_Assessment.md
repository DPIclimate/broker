# **Elaboration Phase Status Assessment**
### 1\. Assessment against Objectives of the Elaboration Phase 
#### 1\.1 **Has ‘end-to-end production level support for the most critical, core (risky, difficult) use case, using the chosen software architecture, in the intended production environment’ been achieved?**
Yes, we have achieved this objective. This is demonstrated in a short video walkthrough which may be accessed from here: 

*LINK - TO VIDEO*

During the Inception Phase, we identified message parsing/TSDB insertion as the critical core use case. This is because: 

- It is the core of the application, without it, all other features are meaningless
- It is run the most often, receiving messages 24/7 from IoT sensors
- Failure of this process could mean missed messages and missing data
- Failure to correctly implement TSDB could mean missing data, or inaccurate data rendering it useless.

We identified microservice, publish/subscribe and narrow waist as a feasible approach to addressing the requirements of the projects as outlined in the updated and continuing Architectural Notebook, which may be accessed here:* 

[*LINK - GOOGLE DOCS](https://docs.google.com/document/d/1se1a30kLpGDpuD1ftnsQPyrReufzt8FG/edit) *| [LINK - GIT VERSION*](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/docs/Final_Architecture_Notebook.md)*

The main architectural elements which are demonstrated by the executable architecture are:

- microservice design
- publish/subscribe design

Those aspects of the architecture not addressed include:

- narrow waist design - our process is inside the narrow waist section.

Correct support for the CCRD use case by the executable architecture was achieved as demonstrated and documented in the following user acceptance tests. 

- Send a Valid Message,
- Send an Invalid Message,
- Send both Valid and Invalid Messages,

Actual test results can be accessed from here: 

[*LINK - GOOGLE DOCS](https://docs.google.com/document/d/1dHWcsnB4cbF50cXL5-Y8rE1BBmUydstv/edit) *| [LINK - GIT VERSION*](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/docs/UAT-Scenario-1.md)*

#
#### 1\.2 **Have all critical and significant project risks been addressed and mitigated?**
<a name="_gjdgxs"></a>The following list identifies the most critical and significant product, technical and project management risks to the project. Mitigation strategies identified and applied and the current status of the risk are also listed. Click links for complete table.

[*LINK - GOOGLE DOCS](https://docs.google.com/spreadsheets/d/1Pmiav81E3mrjCtWAaI6k3QF2Zgjf46zK/edit#gid=257882527) *| [LINK - GIT VERSION*](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/docs/Revised%20Risk-List.xlsx)*

![](https://github.com/ZakhaevK/itc303-team3-broker/blob/master/303/docs/media/risk_list_truncated.png?raw=true)

#### <a name="_f1l1dkdjp3sd"></a>1.3 **Have the initial Vision, Requirements (Scope), or Architecture changed?**
During the Elaboration Phase, our understanding of the projects aims evolved as follows:

***Vision***

|**Change**|**Reason**|
| :-: | :-: |
|-|The vision has remained the same, to choose and implement a time series database such that it adds value to the IoTa framework.|

***Requirements (Functional)***

|**Change**|**Reason**|
| :-: | :-: |
|Removed FDT requirement|Sponsor has informed that this is not required, due to reasons outside our control|
|Added requirement of graphing to existing web app|Stretch goal to provide more work|
|Reprocessing of IoTa messages has possibly been cancelled|Sponsor has informed that this is currently not required, but they will think about whether we need to add it - implementing causes too many issues with other teams' projects.|

***Requirements (Non-Functional)***

|**Change**|**Reason**|
| :-: | :-: |
|-|The non-functional requirements remain the same as when we started the project.|

***Architecture***

|**Change**|**Reason**|
| :-: | :-: |
|-|We are bound by existing architecture.|

#
#### 1\.4 **Have the initial Project Plan or Master Test Plan changed?**
During the Elaboration Phase, our understanding of the best way to implement the project evolved as follows:

***Project Plan***

|**Change**|**Reason**|
| :-: | :-: |
|Reworked construction phases to condense the testing and analysis of the differing TSDB|<p>Condensing saves a whole lot of time, and we would have required the amount of time originally allocated.</p><p></p><p>Removed a lot of redundancy.</p>|
|Reworked construction phases to better use time for implementing, testing and resolving issues with the chosen TSDB.|Better use of our time, allocated more time on implementing ensures a much more complete project reducing risk.|

***Master Test Plan***

|**Change**|**Reason**|
| :-: | :-: |
|Added TSDB selection criteria|Required formalising what we value in a TSDB now that we have a firmer grasp of time series databases, our project architecture and requirements|

#
### 2\. Deliverables
#### 2\.1 Project Vision
***Key Points about deliverable***

|**Key Points**|
| :-: |
|<p>- There were several minor changes to the document that are derived from a better understanding of the project.</p><p>- Requirements have changed quite a bit from the original documentation, with additional tasks, and removal of several. This has expanded and refined the overall vision.</p><p>- Time-series database criteria was added, to give it more of a presence within the vision due to importance.</p>|

***Issues we encountered in producing/documenting***

|**Issues**|
| :-: |
|<p>- Removed some requirements due to reasons outside of our control, leaving the project feeling a little bare.</p><p>- References to importing of data from the IoTa database still exist, but DPI has noted it may not be necessary, and will let us know in the future.</p>|

#### <a name="_xfqxrndkq9i2"></a>2.2 Requirement Model
***Key Points about deliverable***

|**Key Points**|
| :-: |
|- There are several minor changes throughout the document to reflect changes in requirements and understanding - most notably, removal of FDT requirement, addition of CCRD section and use case.|

***Issues we encountered in producing/documenting***

|**Issues**|
| :-: |
|-|

#### <a name="_9o2rl0qpeqzv"></a>2.3 Final Architecture
***Key Points about deliverable***

|**Key Points**|
| :-: |
|<p>- A significant portion of this document has been reworked as we gained a much more complete understanding of the architectural requirements.</p><p>- We have left in one part (Postgres Decoder) that may not actually be actioned, we are awaiting confirmation</p><p>- We are still bound by existing IoTa architecture and rules.</p>|

***Issues we encountered in producing/documenting***

|**Issues**|
| :-: |
|- We were a little slow at confirming and communicating with DPI, there were some misunderstandings which caused a few changes to the architecture.|
#
#### <a name="_rz05m85zyug7"></a>2.4 Risk List
***Key Points about deliverable***

|**Key Points**|
| :-: |
|<p>- Risks were changed in accordance to their current/previous/future expectations</p><p>- Overall document remains very similar to the previous version.</p><p>- Result of revision shows our risks are vastly reduced in number compared to the inception phase.</p>|

***Issues we encountered in producing/documenting***

|**Issues**|
| :-: |
|- Some revised options were removed after implementation, as in discussion we found it wasn’t necessary to distinguish them from other risks due to now being standard requirements.|

#### <a name="_sfemu4l95m8b"></a>2.5 Master Test Plan
***Key Points about deliverable***

|**Key Points**|
| :-: |
|<p>- Added TSDB selection section to have some formal information about criteria and testing of the TSDBs</p><p>- Beyond the TSDB section, only minor changes to improve documents accuracy and detail.</p>|

***Issues we encountered in producing/documenting***

|**Issues**|
| :-: |
|-|

#### <a name="_y4d9slbsdj1o"></a>2.6 Executable Architecture
***Key Points about deliverable***

|**Key Points**|
| :-: |
|<p>- CCRD Implemented in Prometheus, InfluxDB, Timescale, QuestDB</p><p>- Good use of feature branches for separation.</p><p>- Teamwork with video was rather good.</p><p>- We gained a solid amount of knowledge and experience with the IoTa framework, confident of success.</p>|

***Issues we encountered in producing/documenting***

|**Issues**|
| :-: |
|<p>- Dealing with four people handling four different database implementations causes issues with being able to assist one another.</p><p>- Dealing with four different TSDB means different implementations of them, this makes testing a little redundant.</p><p>- Version control practices could be improved.</p><p>- Slow implementation or trouble with implementing certain aspects such as integration with IoTa or testing.</p>|

#### <a name="_2d82pygups5v"></a>2.7 User Acceptance Tests
***Key Points about deliverable***

|**Key Points**|
| :-: |
|<p>- UAT seems bare, however unfortunately our use case is rather bare (receive message, process message, insert into TSDB, confirm success/failure)</p><p>- The UAT document is formatted quite well and will soon show all four sets of UAT results.</p><p>- Script guide section was added to assist in each step for each DB, and keep script steps tidy.</p>|

***Issues we encountered in producing/documenting***

|**Issues**|
| :-: |
|- Slow to complete or add results to UAT documents causing delay in completion of a number of deliverables.|
#### <a name="_9p0aurv5l0zj"></a>2.8 Unit Tests / Integration Tests
***Key Points about deliverable***

|**Key Points**|
| :-: |
|<p>- Unit tests fully test functions we’ve implemented ie message parsing, insertion</p><p>- Integration tests work inside our test environment (test environment is identical to live environment bar logins and persistence)</p><p>- There are no unit tests for the Prometheus branch due implementation being done by configuration, and can only do integration tests.</p>|

***Issues we encountered in producing/documenting***

|**Issues**|
| :-: |
|<p>- A little slow to finalise testing and upload results.</p><p>- Some parts took quite a lot longer than anticipated.</p><p>- Inconsistencies between tests exist due to different branches.</p>|

#### <a name="_1lr3bbz2vcdd"></a>2.9 Project Plan
***Key Points about deliverable***

|**Key Points**|
| :-: |
|<p>- Mostly ‘construction phases’ changed to make better use of time, and be more realistic in how construction would occur.</p><p>- Some changes made to previous iterations where actual completed work items drew from later iterations listed tasks, where it made sense to do them early.</p>|

***Issues we encountered in producing/documenting***

|**Issues**|
| :-: |
|- Not having kept document up to date throughout iterations made it difficult to update all at once, after several iterations of tweaks.|

#
#### <a name="_d12t7526dfj"></a>2.1 Elaboration Phase Project Assessment
***Key Points about deliverable***

|**Key Points**|
| :-: |
|<p>- Basically a summary of other documents, reflection on elaboration</p><p>- Honest input on elaboration, and current state of documents.</p><p>- Feeling confident about the project success and the standard of the documents.</p><p>- No changelog as this document has been left until last minute, creation and changes are done at same time.</p>|

***Issues we encountered in producing/documenting***

|**Issues**|
| :-: |
|- Waiting on other documents to be able to complete|
#
### 3\. General Issues

|**Issue**|**Status**|
| :-: | :-: |
|Trello board is not being as actively updated as it should -- ideally it should be a live view on tasks, instead it is an outdated view|Ongoing - managing|
|Communication -- this is definitely being improved upon as workload increases, however at times it could be better.|Ongoing - managing|
|Pushes to repos -- both with git and google drive, work items are not being kept up to date in common areas.|Ongoing - managing|

## 4 Summary – Overall Project Progress
***Progress against Elaboration Phase - Summary***

The initial parts of the elaboration phase were rather successful, we have partially implemented all of our TSDB we wish to test, CCRD are working on all of them, as of writing this, testing and UAT are nearly complete.

The second half of the elaboration phase slowed down to some degree, we’re now pushing to reach deadlines on multiple fronts such as documentation, testing and administration. We were slow to confirm things with DPI and although this did not cause significant issues, some time was wasted on parts that are now removed.

***Ongoing Risks - Summary***

We have several ongoing risks that still need mitigation, such as skills and knowledge, and lack experience in delivering a final product and TSDB implementation. 

As a team however, we are confident in our ability to complete this project to a high standard. The major technical and understanding risks have been dealt with in various means.

The team plans to continue to mitigate any existing risks and also any unforeseen risks that may arise.

***Changes to Project Scope and Project Plan - Summary***

Original project plan was a little naive, we have improved the construction phases to ensure a good use of time and allowing for logical and realistic feature implementations.

We’ll prepare each implementation and the tests, then move onto testing and analysing results, from there we’ll pick and finalise a specific implementation and move onto developing the extra requirements such as API, backup and visualisation.

The project scope has narrowed due to both understanding but also removal of some requirements. In a perfect world, the two projects for IoTa would have been one single project to ensure a more well balanced workload for a team to complete in multiple semesters.

***Status of Ongoing Issues - Summary***

The only real issues that currently exist are:

- Poor use of updating tasks - i.e Trello, however this iteration has been much improved - we’re still actively improving this, and as we move onto construction, use of Trello should become easier.
- Long periods of no communication - this again should improve in construction phases as talking about documents and architecture can be tedious.
- Long periods of no pushes - without pushing to git, work can only be done by one person instead of being team wide.

