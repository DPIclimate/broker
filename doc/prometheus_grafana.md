# Prometheus

Prometheus gathers and serves metrics for each microservice over a client HTTP server which is retrieved from a
Prometheus server.

The Prometheus client has been added to the Python `requirements.txt` file at `broker/images/restapi/requirements.txt`
and implemented through `npm install prom-client` at `broker/images/ttn_decoder/Dockerfile` which will enable the import
of the client on each of the Python and Node.js microservices.

The Prometheus server has been added to `broker/compose/docker-compose.yml` and is running on and can be accessed from
port `9090`.

## Microservices

Listed below is each microservice that runs a Prometheus client, what metrics it serves, and the port it serves them on.
Each metric is a counter that increments or decrements in various functions within the microservice.

### restapi

- `/broker/src/python/restapi/RestAPI.py`
- port `8000`
- `request_counter` = counts total number of messages made to the system.
- `errors_counter` = counts total number of errors encountered while processing messages

### ttn_webhook

- `broker/src/python/ttn/WebHook.py`
- port `8001`
- `request_counter` = counts total number of messages made to the system

### ttn_processor

- `broker/src/python/ttn/AllMsgsWriter.py`
- port `8002`
- `request_counter` = counts total number of messages made to the system

### ydoc

- `broker/src/python/ydoc/YDOC.py`
- port `8003`
- `request_counter` = counts total number of messages made to the system
- `failed_messages_counter` = counts total number of messages that failed during processing
- `new_devices_counter` = counts total number of new devices detected by the system
- `existing_devices_messages_counter` = counts total number of messages received from devices known to the system
- `dropped_messages_counter` = counts total number of messages ignored/discarded without processing
- `published_messages_counter` = counts total number of messages published to RabbitMQ
- `failed_published_messages_counter` = counts total number of messages failed publishing to RabbitMQ
- `errors_counter` = counts total number of errors encountered while processing messages
- `active_connections_gauge` = current number of active RabbitMQ connections. Metric can increase or decrease over time

### wombat

- `broker/src/python/ydoc/Wombat.py`
- port `8004`
- `listener_starts_counter` = counts the number of times the Wombat listener has started.
- `graceful_exit_counter` = tracks the number of times the application has gracefully exited.
- `messages_received_counter` = records the number of messages received from RabbitMQ.
- `messages_acknowledged_counter` = counts the number of messages that have been acknowledged to RabbitMQ.
- `messages_published_counter` = tracks the number of messages that have been published to RabbitMQ.
- `devices_created_counter` = monitors the number of physical devices that have been created in the database.
- `devices_updated_counter` = tracks the number of physical devices that have been updated in the database.
- `exceptions_caught_counter` = counts the number of exceptions that have been caught during the message processing.
- `message_processing_errors_counter` = records the number of errors that have occurred while processing messages,
  particularly when a physical device is not found.

### lm

- `broker/src/python/logical_mapper/LogicalMapper.py`
- port `8005`
- `messages_received_counter` = counts the number of messages that the Logical Mapper has received for processing from
  the physical_timeseries queue.
- `messages_published_counter` = tracks the number of messages that the Logical Mapper has successfully published to the
  logical_timeseries queue.
- `messages_acknowledged_counter` = records the number of messages that the Logical Mapper has acknowledged to RabbitMQ,
  indicating they have been processed successfully.
- `messages_stored_counter` = monitors the number of messages that have been stored in the physical_timeseries table in
  the database.
- `logical_devices_updated_counter` = tracks the number of logical devices that have been updated in the database by the
  Logical Mapper.
- `message_processing_errors_counter` = counts the number of errors that have occurred during the message processing
  phase.
- `no_device_mapping_counter` = records the number of messages that were processed without an existing device mapping.
- `logical_mapper_starts_counter` = monitors the number of times the Logical Mapper script has been started.
- `logical_mapper_exits_counter` = tracks the number of times the Logical Mapper script has exited or terminated.

### delivery

- `broker/src/python/delivery/UbidotsWriter.py`
- port `8006`
- `messages_processed_counter` = incremented every time a message is successfully parsed and accepted for processing.
- `messages_forwarded_counter` = incremented every time a message is successfully forwarded to Ubidots
- `messages_acknowledged_counter` = incremented every time a message is acknowledged to RabbitMQ, indicating successful
  handling.
- `message_processing_errors_counter` = incremented whenever there's an error while processing a message.
- `ubidots_writer_starts_counter` = incremented when the Ubidots writer script starts
- `ubidots_writer_exits_counter` = incremented when the Ubidots writer script exits.

### frred

- `broker/src/python/delivery/FRRED.py`
- port `8007`
- `rabbitmq_connection_attempts` = counts the number of connection attempts to RabbitMQ.
- `rabbitmq_successful_connections` = counts the number of successful connections to RabbitMQ.
- `rabbitmq_failed_connections` = counts the number of failed connection attempts to RabbitMQ.
- `messages_received` = counts the number of messages received from RabbitMQ.
- `valid_json_messages` = counts the number of valid JSON messages processed.
- `invalid_json_messages` = counts the number of invalid JSON messages.
- `messages_rejected_finish_flag` = counts the number of messages rejected due to the _finish flag being set.

### ttn_decoder

- `broker/src/js/ttn_decoder/src/index.js`
- port `3001`

# Grafana and Nginx

The Nginx server directs traffic to Grafana as stated in `broker/config/nginx.conf`.

## Accessing the Services

- Grafana can be accessed at http://localhost:3000. Use the username `admin` and password `password` to log in
- Nginx can be accessed at http://localhost or https://localhost which will redirect to Grafana.
