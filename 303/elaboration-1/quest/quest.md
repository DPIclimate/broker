--- 
### QUESTDB - Initial Review
--- 
#### Overview
- Written in low-latency Java, C++, and Rust (mostly Java)
- Ranked #10 in db-engines.com, officially launched in 2020 though been around since 2014
- Apache 2.0 Licensed (https://www.apache.org/licenses/LICENSE-2.0)
- Uses optimized column-based storage model:
    - each column stored in its own file and own native format
    - new data is appended to bottom of each column
    - tail of the file is loaded into RAM meaning column append is memory write at an address
    - supports random access for reading
    - stored in time partitions - decreases in memory requirements
- Atomocity - will only show changes once committed
- Consistancy assurance limited to QuestDB auto-repairing abnormally terminated transactions.
- Performance:
    - column based means it can handle columns in parallel easily
    - designed to handle datasets for all sizes
    - leverages SIMD, aggregates multiple rows simulatanously
    - QuestDB 7.0 vs influxDB 1.8 vs timescaleDB 2.1 == questdb magnitudes faster
- Compatibility:
    - InfluxDB line protocol, PostgresSQL wire, REST API, CSV upload
    - fairly easy to port existing applications over
    - works with both docker and Kubernetes
- Queries:
    - SQL w/ time series extensions 
    - Web console:
        - SQL ```select``` statements
        - download as CSV
        - chart query results
    - PostgreSQL wire protocol:
        - SQL ```select``` statements
        - ```psql``` via CLI
    - HTTP REST API
        - SQL ```select``` statements as JSON or CSV
        - result paging

#### In terms of our project
##### pros
- Apache 2.0 license
- Open source version, free
- Excellent documentation
- Possibly quickest TSDB of all our options
- Supports lots of good third party tools ie grafana, pandas, prometheus, telegraf
- Community seems active and helpful, several good reviews about the community, may be helpful in answering questions we may have.
- Can detatch partitions for storage
- Our performance needs are pretty minimal, meaning the gains in performance likely not noticable 
- Using SQL lowers learning curve
- SQL Time Series Extensions such as ```latest on, sample by, timestamp search``` and also simpler syntax in some complex SQL operations
- true TSDB build for time series data
- could partition the columns by month making it easier for back up, better performance
- has symbols for repeated strings to reduce size/improve performance
##### cons
- replication still in development -  likely not an issue as it won't be used - database is already backed up into the existing database.
- Smaller project using IoT means less likely to run into new issues so smaller community is not a huge pitfall
- Current version 7.0 is rather young (feb 2023), with 7.1.1 being latest (april 2023) means there's likely more bugs to be discovered/fixed.
- **no built in compression means we'd need to use something like ZFS - compression is a key factor as there's quite a bit of data**
- newer db compared to the other competitors



#### Stretch Goals or things to consider
- Could look at combining it with Grafana via existing web app to have a comprehensive dashboard: https://questdb.io/blog/time-series-monitoring-dashboard-grafana-questdb/
- No built in compression may make it more complex to implement, may not be as good as alternatives
- Would need to implement partitioning and possibly some other features for questdb
- look at how it might be migrated from docker to Kubernetes
- would need to look at implementing some sort of health monitoring (inbuilt)
- would need to plan a schema around our data formatting and requirements

.
#### Up and Running Guide
- run docker container ```docker run -d --rm --name questdb -p 9000:9000 -p 9009:9009 -p 8812:8812 -p 9003:9003 questdb/questdb:7.0.1 >/dev/null```
    - ```--rm``` : remove container after
    - ```--name``` : name container so easier to find/delete it
    - ```-p 9000:9000``` : map local port to container port (REST API & WEB CONSOLE)
    - `9009`: influxDB line protocol, `8812` postgres wire protocl (unused), `9003` minserver health (unused)
    - no volume is set so no data is kept
    - ```questdb/questdb:7.0.1 >/dev/null``` : the image we want to use, send output to nowhere
    - `./start.sh` does this and confirms the container is Running
    - head to `localhost:9000` in browser and should see webconsole running with nothing inside as there's no database
    - `python db.py` will insert all data from `.../docs/sample_messages` into database and print the inserted ones to console.
    - inside webconsole if you run `dpi;` which is just the created tables name, you can view all the inserted data also (~200 rows)
    - within webconsole you can also create a graph from the data by using the UI
    - `./stop.sh` simply runs `docker stop questdb` to stop the docker
