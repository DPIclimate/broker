# IoTa - IoT device management / message transformation and routing

## Overview

IoTa is an IoT device management and message transformation and routing system developed by the [Digital Agriculture team at the NSW Department of Primary Industries](https://www.dpi.nsw.gov.au/dpi/climate/digital-agriculture).

IoTa has been developed in response to the challenges the team encountered while running and maintaining sensor networks in the field and building a research database of timeseries data.

> Note: References to commerical vendors in this documentation are not recommendations or endorsements.

These challenges include:

* Multiple communications protocols including LoRaWAN via The [Things Stack Community Edition](https://www.thethingsnetwork.org/docs/quick-start/), NB-IoT with MQTT, and polled sources via vendor APIs.

* Multiple message formats including base64 encoded binary, JSON, and CSV.

* The replacement of devices in the field, while requiring the data from that location to continue to be recorded in the same series of data in the timeseries database.

* Changes in IoT data storage and dashboardings platforms.

* The potential necessity for reprocessing messages due to bugs in the message decoders.

* Management and monitoring of the system at runtime.

The design of IoTa attempts to address these challenges with a 'narrow waist' architecture where the front- and back-end processors of the system (implemented as microservices) accept messages from varied sources and deliver the timeseries data to multiple destinations, and the narrow waist uses IoTa's own message format and a physical to logical device mapping layer.

Message exchanges and queues are used as the service coupling mechanism, carrying timeseries data in a normalised format that front- and back-end microservices must emit or accept. The use of persistent exchanges and message queues provides some amount of resiliency to the system.

The scale of the Digital Agriculture project is relatively small - comprising some few hundred devices in the field - so the rate of messages and the performance required from even the busiest components are modest. The implementation reflects this, having enough performance and resiliency to support our use-case while exploring solutions to the challenges mentioned above.

To address the problem of routing the data from different devices in the field - for example after replacing a broken device - to the same final destinations IoTa introduces the notion of physical and logical devices. Physical devices are the devices in the field, sending data via some means to be accepted by the front-end processors. Logical devices
represent a device in a destination system or database such as a tank sensor or weather station whose timeseries data
may be provided by different physical devices over time as the phyiscal devices are replaced for maintenance purposes.

Due to the disparate nature of sources and destinations, IoTa has a minimalistic view of devices, comprising an id, name, location, and a last seen timestamp. Physical devices also record their 'source' and some source-specific information to allow fast device lookups to be performed based upon information in an incoming message. Each device has a map of free-form properties associated with it that is available for use by the various components of the system.

## Terminology

* Sensor: The term 'sensor' is used to describe a real device deployed in the field. In reality this is likely to be a microcontoller system with RF communications and some number of actual sensors attached such as soil moisture probes, water salinity sensors, liquid level sensors etc.

* Physical device: A physical device is IoTa's representation of a sensor. Front-end processors create physical devices as necessary in response to incoming telemetry messages.

* Logical device: A logical device is IoTa's representation of a destination for timeseries telemetry. It generally represents a sensor in a location such as a water tank or a buoy in a river, and a series of sensors/physical devices will be assoiated with that location over time as maintenance takes place. Telemetry sent to destination systems such as IoT platforms are recorded against logical devices so a coherent timeseries is maintained.

* Mapping: Physical devices are mapped to logical devices, and this mapping is updated when a new physical device appears due to field maintenance. Mappings can also be temporarily or permanently broken to stop messages from a physical device reaching the destination systems, such as when a device is retired or is being reconfigured.

## System architecture

### Front-end processors

The front-end processors are responsible for accepting or fetching messages from the various telemetry sources. The majority of our sensors are deployed connected to LoRaWAN nodes whose messages are received via the The Things Stack Community Edition. We have a growing number of sensors attached to YDOC NB-IoT nodes, and a few sensors whose telemetry must be retreived via polling vendor REST APIs.

Each front-end processor is responsible for accepting or retrieving messages from its source and transforming those messages into IoTas own message format for use throughout the remaining processing stages, before publishing the messages to an exchange leading into the mid-tier narrow-waist processes.

Front-end processors are responsible for creating physical devices in IoTas database. This must be done when a message from a new device is received. Each physical devices has a map that can be used for storing free-form information against the device. Front-end processors may use this to store source-specific device information, the last message received, etc.

Finally, front-end processors are responsible for generating and assigning the correlation id to each message as it is received, and should record every message along with its correlation id in the  `raw_messages` database table. This should be done as soon as possible so the message has the best chance of being stored somewhere before any errors cause the processor to abort processing that message.

### Mid-tier processors

There is currently one mid-tier processor, the logical mapper. The logical mapper's job is to determine where to send the telemetry received from a physical device. This decision is informed by a table in the database that maps a physical device to a logical device. This mapping must be updated when a physical device is replaced in the field so that data from the new device flows to the same destination.

The mapping is maintained manually using a CLI tool or the management webapp. For example, this tool provides a command to create a logical device based upon an existing physical device and then map the two. The reason this is not done automatically is because when a sensor is replaced in the field and a new physical device is created by a front-end processor, the telemetry from that new sensor/physical device should flow to the same logical device, not a new one.

### Back-end processors

A back-end processor is responsible for writing timeseries data to destinations such as IoT platforms or locally hosted timeseries databases.

There are currently two back-end processors:

* [delivery.UbidotsWriter](src/python/delivery/UbidotsWriter.py) writes to our current IoT platform, [Ubidots](https://www.ubidots.com/).

* [delivery.FRRED](src/python/delivery/FRRED.py) writes the messages to a filesystem directory defined by the `DATABOLT_SHARED_DIR` environment variable, where the Intersect DataBolt process is polling for them. For example, to write message files to the /home/abc/databolt/raw_data directory set `DATABOLT_SHARED_DIR=/home/abc/databolt` in the `compose/.env` file.

### Inter-service communications

Message queues and exchanges are used for message flow through the system. [RabbitMQ](https://rabbitmq.com/) is used as the message broker, and provides the persistence mechanism for the messages.

Two main exchanges are used:

* `physical_timeseries` is used to send messages from the front-end processors to the mid-tier.

* `logical_timeseries` is used to send messages from the mid-tier to the back-end processors.

These exchanges are fan-out exchanges, meaning any number of microservices may bind message queues to them to receive messages. This was done to allow the possibility of timeseries data to be delivered to multiple destinations.

The message exchanges and queues are declared as persistent, and the exchanges require positive acknowledgement of a message or it will be re-delivered to a subscriber.

> This can be a nuisance if a processor fails to handle a message due to either a bug or a malformed message - if the processor NACKs a message that cannot be processed without specifying it should not be re-delivered then RabbitMQ and the processor will become stuck in an endless loop with RabbitMQ continually re-delivering the message as soon as the processor NACKs it.

A third exchange, `ttn_raw` is used internally by the Things Stack front-end processor. Additionally, HTTP is used for communication internally within this same front-end processor for calling uplink decoders.

RabbitMQ also acts as an MQTT broker for sources that publish telemetry via MQTT.

### Database

IoTa uses a [PostgreSQL](https://www.postgresql.org/) database to store device metadata and raw messages.

### Reverse proxy

A reverse proxy is required to terminate TLS connections for webhooks, the REST API, the management webapp, and the MQTT broker. [nginx](https://www.nginx.com/) works well, and configuration details are provided in [doc/nginx.md](doc/nginx.md).

### Normalised message format

Messages from sensors come in many formats and protocols, but all essentially encode information about the identity of the sender, one or more timestamps, and data.

In some cases the sender's identity is not included in the message itself but is encoded in the delivery mechanism, such as an MQTT topic name.

The normalised message format used by IoTa includes the following information:

* The physical device id.

* The logical device id, for messages sent to the `logical_timeseries` exchange after a physical to logical device mapping has been made.

* A default timestamp for any timeseries values in the messages without their own timestamp. The timestamp is in ISO-8601 format.

* A set of timeseries data points with a name, a value, and optionally a timestamp overriding the default timestamp.

* A correlation value (a UUID) that can be used to trace the timeseries values from this message back to the message as received from the sensor, and to log entries from the various microservices. In our case this correlation value is recorded against the value in Ubidots using the Ubidots dot context feature.

The normalised messages are encoded as JSON objects before being published to a message exchange.

An example of a message in this standard format:

```
{
  "broker_correlation_id": "83d04e6f-db16-4280-8337-53f11b2335c6",
  "p_uid": 301,
  "l_uid": 276,
  "timestamp": "2023-01-30T06:21:56Z",
  "timeseries": [
    {
      "name": "battery (v)",
      "value": 4.16008997
    },
    {
      "name": "pulse_count",
      "value": 1
    },
    {
      "name": "1_Temperature",
      "value": 21.60000038
    }
  ]
}
```

## Installation

A simple installation of IoTa is achieved by cloning the GitHub repository, and installing a web server to act as a TLS connection termination point and reverse proxy if desired.

This is how it is deployed by the Digital Agriculture team. We hope the containerised nature of the system assits in deploying to a cloud service but we have not had a reason to do that - a simple docker compose deployment is sufficient for our scale.

docker must be installed for IoTa to run, the version of which is recent enough that the `docker compose` command is supported.

> The [ttn-formatters](https://github.com/DPIclimate/ttn-formatters) repo should be cloned in the same directory as the broker
> repo, ie the ttn-formatters and broker directories share the same parent directory.
> 
> If this is not done the ttn_processor and ttn_decoder logs will get errors for every uplink received. If the message from TTN
> has decoded values in it, these values will be used.

```
$ git clone https://github.com/DPIclimate/broker.git
$ git clone https://github.com/DPIclimate/ttn-formatters.git
```

## Configuration

### Container environment variables

The main point of configuration is the file `compose/.env`. Many variables have default values and can be left as-is. It is important to set the passwords to a secure value. The hostnames should be left at their defaults unless the docker-compose file services are also updated to reflect the hostnames.

This .env file must also be symlinked into the `compose/production` and `compose/test` directories.


### Docker volumes

To preserve the state of PostgreSQL and RabbitMQ between `docker compose down` and `docker compose up` commands, external volumes are used by the database and RabbitMQ containers when running in production mode.

These external volumes must be created before running IoTa in production mode, using the commands:

```
$ docker volume create broker_db
$ docker volume create mq_data
```

The Intersect DataBolt delivery processor requires a volume mapped to a directory shared with the DataBolt container. The `DATABOLT_SHARED_DIR` environment variable must be set to the fully qualified path name of this directory, for example `DATABOLT_SHARED_DIR=/home/abc/databolt`.


# Running IoTa

## run.sh

IoTa is started using the `run.sh` script.

`run.sh` takes a single argument, either `production` or `test`.

`run.sh production` starts IoTa in 'production' mode, which starts all the front-end (except GreenBrain), mid-tier, and back-end processors and exposes various IP endpoints to the host for use by the reverse proxy. 

`run.sh test` starts a test instance of IoTa. This can be done on the same host as a production instance but this is not recommended. The test deployment starts an additional container, `test-x-1`, that can be used for running unit tests or other Python scripts. A test instance still runs any back-end processors; you may wish to either disable these or point them at staging environments while becoming familiar with the system in order to avoid polluting a production timeseries database or IoT platform. Test mode uses temporary volumes for the database and message queues, so data will not survive a `docker compose down` command. Less networking ports are exposed, and some port numbers are changed so they do not conflict with those used in production mode.

In either mode the script runs a `docker compose logs -f` command, leaving the log files scrolling up the screen. You can safely `ctrl-c` out of this and the containers will keep running.

## dc.sh

A script called `dc.sh` exists in both the `broker/compose/production` and `broker/compose/test` directories. This is a convenience script for running `docker compose` commands with the correct docker-compose file arguments and in the correct directory.

Examples:

* `compose/production/dc.sh ps` to show which production containers are running.

* `cd compose/test; ./dc.sh restart x` to restart the test-x-1 container.

* `./dc.sh down` to bring the `docker compose` stack down. The stack that is stopped depends on whether you are in the `broker/compose/production` or `broker/compose/test` directory.

* `./dc.sh logs -f lm delivery` follow the logs for the logical mapper and Ubidots delivery containers.

# broker-cli

A python script called `broker-cli` can be used to query and update the device data. It must be run in a container using a command similar to:

```
docker exec prod-lm-1 python -m broker-cli pd ls --plain
```

If a container is running a python process, it can be used for running `broker-cli`. It makes no difference which python-enabled container is used, so this document will always use lm_1 - `test-lm-1` or `prod-lm-1`.

The `broker/src/python` directory is mounted into the python-based containers and is the current working directory for processes in those containers. If you wish to provide a file to a command you can place the file in the `broker/src/python` directory and have the command find it:

```
docker exec prod-lm-1 python -m broker-cli pd create --file new_device.json
```

If a command can take JSON via stdin using `--file -` then you must run the command from a shell running in the container:

```
host$ docker exec -it prod-lm-1 bash
broker@529308294:~/python$ cat updated_device.json | python -m broker-cli pd up --puid 123 --file -
```

The script functions are broken up into a multi-level set of commands, with flags used to pass in values. The --help flag to print the available commands and flags.

From here on, the docker part of the command line is omitted, and examples will start with `broker-cli`.

## Physical devices

The `pd` command is used to work with physical devices. The subcommands are:

* `get --puid uid [--properties]` returns the complete JSON representation of a physical device identified by `uid`. Unless the `--properties` flag is used the properties field is omitted to reduce clutter in the output. 

* `lum [--source source] [--properties] [--plain]` lists currently unmapped physical devices. A JSON list (the default), or a plain single line per device list of devices is the output. May optionally be filtered by source. Unless the
  `--properties` flag is used the properties field is omitted to reduce clutter in the output. 

* `ls [--source source] [--properties] [--plain]` lists mapped and unmapped physical devices, with the option of filtering by source. Plain mode shows one device per line, with the mapped logical device (if any). Unless the
  `--properties` flag is used the properties field is omitted to reduce clutter in the output. 

* `create --file filename | --json '{"name": "...", ...}'` creates a physical devices based upon a JSON object provided to the command. See the example below for the structure of the JSON object. The flags  `--file` and `--json` are mutually
  exclusive. Use `--file -` to read JSON from stdin.

* `up --puid uid --file filename | --json '{ ... }'` updates the physical device identified by uid based upon the JSON object provided to the command. Only the fields present in the JSON object will be updated in the database. The flags  `--file` and `--json` are mutually exclusive. Use `--file -` to read JSON from stdin.

* `rm --puid uid` deletes the physical device indentified by uid.

_Examples_:

`broker-cli pd get --properties --puid 6`

> Fetches the physical device with uid 6 and prints the complete JSON representation.

`broker-cli pd lum`

> Prints a list of all unmapped physical devices in JSON format, without the properties field.

`broker-cli pd lum --source ttn`

> Prints a list of all unmapped TTN physical devices in JSON format.

`broker-cli pd ls`

> Prints a list of all physical devices in JSON format, excluding the properties field.

`broker-cli pd ls --source ydoc --plain`

> Prints a list of all YDOC devices in a plain text format, one device per line, including the current mapping to a
> logical device, if any.

`broker-cli pd create --json '{ "source_name": "ttn", "name": "Test device", "location": { "lat": -39.769108, "long": 147.920245 }, "source_ids": { "app_id": "ttn-app-id", "dev_id": "ttn-device-id", "dev_eui": "ttn-dev-eui-in-hex" } }'`

> Creates a new physical device and prints the JSON object describing the newly created device. The new device's uid is included in this output.

`broker-cli pd create --file new_device.json`

> Creates a new physical device from the JSON in `new_device.json` and prints the JSON object describing the newly created device. The new device's uid is included in this output.

`broker-cli pd up --puid 123 --json '{ "name": "XYZ", "last_seen": "2022-05-06T10:30+10:00" }'`

> Updates the name and last_seen fields of the physical device identified by uid 123. The updated device JSON is printed.

`cat updated_device.json | python -m broker-cli pd up --puid 123 --file -`

> Updates the physical device identified by uid 123 with changes contained in the file updated_device.json. The updated device JSON is printed. This command would be have been run while logged into the container.

`broker-cli pd rm --puid 123`

> Deletes the physical device with uid 123 and prints the JSON object describing the (now deleted) device.

## Logical devices

The `ld` command is used to work with logical devices. The subcommands are:

* `get --luid uid [--properties]` returns the complete JSON representation of a logical device identified by `uid`. Unless the `--properties` flag is used the properties field is omitted to reduce clutter in the output. 

* `ls [--source source] [--properties]` lists mapped and unmapped logical devices, with the option of filtering by source. The properties field is omitted unless the `--properties` flag is used to reduce clutter in the output. 

* `create --file filename | --json '{"name": "...", ...}'` creates a logical devices based upon a JSON object provided to the command. See the example below for the structure of the JSON object. The flags  `--file` and `--json` are mutually
  exclusive. Use `--file -` to read JSON from stdin.

* `up --luid uid --file filename | --json '{ ... }'` updates the logical device identified by uid based upon the JSON object provided to the command. Only the fields present in the JSON object will be updated in the database. The flags  `--file` and `--json` are mutually exclusive. Use `--file -` to read JSON from stdin.

* `rm --luid uid` deletes the logical device indentified by uid.

_Examples_:

`broker-cli ld get --properties --luid 6`

> Fetches the logical device with uid 6 and prints the complete JSON representation.

`broker-cli ld ls`

> Prints a list of all logical devices in JSON format, excluding the properties field.

`broker-cli ld create --json '{ "name": "Test device", "location": { "lat": -39.769108, "long": 147.920245 } }'`

> Creates a new logical device and prints the JSON object describing the newly created device. The new device's uid is included in this output.

`broker-cli ld create --file new_device.json`

> Creates a new logical device from the JSON in `new_device.json` and prints the JSON object describing the newly created device. The new device's uid is included in this output.

`broker-cli ld up --luid 123 --json '{ "name": "XYZ", "last_seen": "2022-05-06T10:30+10:00" }'`

> Updates the name and last_seen fields of the logical device identified by uid 123. The updated device JSON is printed.

`cat updated_device.json | python -m broker-cli ld up --luid 123 --file -`

> Updates the logical device identified by uid 123 with changes contained in the file updated_device.json. The updated device JSON is printed. This command would be have been run while logged into the container.

`broker-cli ld rm --luid 123`

> Deletes the logical device with uid 123 and prints the JSON object describing the (now deleted) device.

## Device mappings

The `map` command is used to work with physical devices. The subcommands are:

* `ls (--puid p_uid | --luid l_uid)` display the current mapping for the specified device. Either a physical or logical
  device identifier may be provided, but not both. The mappings are displayed as a JSON object containing the physical
  and logical devices, and the start and end times of the mapping.

* `start --puid p_uid --luid l_uid` maps the physical device identified by p_uid to the logical device identified
  by l_uid, with a start time of 'now'. Messages from the physical device will start flowing to the logical device. The
  new mapping is printed as a JSON object.

* `end (--puid p_uid | --luid l_uid)` end the current mapping for the specified device. Either a physical or logical
  device identifier may be provided, but not both.

_Examples_:

`broker-cli map ls --puid 154`

> Displays the current mapping, if any, for physical device identified by uid 154.

`broker-cli map ls --luid 123`

> Displays the mapping history, if any, for the logical device identified by uid 123.

`broker-cli map start --puid 154 --luid 123`

> Maps phyiscal device 154 to logical device 123. Any existing mapping for either device is ended.

`broker-cli map end --puid 154`

> Ends the current mapping, if any, for physical device identified by uid 154.

# User Authentication

The broker implements authentication to control access to the API endpoints. The user is created on the broker-cli and then an API request prives a username and password to obtain an authorization token which can be used for subsequent requests.

## Broker CLI

The `users` command is use to manage users. Subcommands are:

- `add -u username -p password` used to craete a new user. Creating a new user will generate an authenticatino token for the user to use. Use the `-d` option to disable the token upon creation.

- `rm -u username` command is used to remove a user

- `token -u username (--refresh | --disable | --enable)` used to enable/disable a users token as weel as refresh their token.

- `chng -u username -p new_password` used to change the users password

- `ls` used to list all users in the broker

_Examples_:

`broker-cli add -u my_user -p super_strong_password`

> Creates a user called 'my_user' and has the password 'super_strong_password'

`token -u my_user --refresh`

> Refreshes the authentication token required for my_user to authenticate with the system

## Authenticating with API

To authenticate with the API you must obtain a users token at `/broker/api/token`. This token can then be used for subsequent requests with the API

### Obtaining Bearer Token

`/broker/api/token` uses Basic HTTP Auth to send the username and password. 

_Example Request_:

```bash
curl -X 'GET' \
  'http://10.211.55.3:5686/broker/api/token' \
  -H 'accept: application/json' \
  -H 'Authorization: Basic bXlfdXNlcjpzdXBlcl9zdHJvbmdfcGFzc3dvcmQ='
```

> `Basic bXlfdXNlcjpzdXBlcl9zdHJvbmdfcGFzc3dvcmQ=` is the base64 encoded string of  `my_user:super_strong_password`

_Example Response_:

```bash
"0b81e933c7b79bb20a98cba7936ce3bfc2098b7ed10fb46548d22f0aaaf19f1e6f627ec3d9ef7d5247f8c48cdbc674251f15804baf3fe4bede5c5c2c7490378e"
```

> This is the token to be used on subsequent requests with the API

### Authenticating

Now that a token has been obtained we can make a request to other endpoints, for example `/broker/api/physical/sources`. Instead of Basic HTTP Auth we will use Bearer Authentication.

_Example Request_:

```bash
curl -X 'GET' \
  'http://10.211.55.3:5686/broker/api/physical/sources/' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer 0b81e933c7b79bb20a98cba7936ce3bfc2098b7ed10fb46548d22f0aaaf19f1e6f627ec3d9ef7d5247f8c48cdbc674251f15804baf3fe4bede5c5c2c7490378e'
```

# Unit tests

There are unit tests for the database interface and the REST API. To run these, use the following commands while a set of test containers are running (via `run.sh test`):

```
$ docker exec test-x-1 python -m unittest TestDAO
$ docker exec test-x-1 python -m unittest TestRESTAPI
```
