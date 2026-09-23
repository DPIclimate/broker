# Tago poller

The Tago poller reads the `export` variable from each configured TagoIO device,
converts its CSV value to a physical timeseries message, and publishes the
message to the `pts_exchange` RabbitMQ exchange.

Each device token represents one physical device. Tokens are secrets and are
never written to the spool or the database.

## Configuration

Set these variables in `compose/.env`:

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `TAGO_DEVICE_TOKENS` | Yes | | Comma-separated device tokens. |
| `TAGO_SPOOL_HOST_DIR` | No | `../data/tago-spool` | Host directory mounted into the container. |
| `TAGO_API_BASE_URL` | No | `https://api.us-e1.tago.io` | Use `https://api.eu-w1.tago.io` for the EU region. |
| `TAGO_POLL_INTERVAL` | No | `300` | Seconds between successful poll cycles. |
| `TAGO_INITIAL_LOOKBACK` | No | `86400` | Initial history window in seconds for a new device. |
| `TAGO_PAGE_SIZE` | No | `1000` | Records requested on each API page. |
| `TAGO_REQUEST_TIMEOUT` | No | `30` | HTTP timeout in seconds. |
| `TAGO_MAX_BACKOFF` | No | `900` | Maximum error retry delay in seconds. |

Start the service with the `tago` Compose profile.

## Durable spool

The container uses `/var/spool/tago`, mounted from `TAGO_SPOOL_HOST_DIR`.

- `pending/` contains complete Tago API responses and per-record progress.
- `quarantine/` contains malformed records and their validation error.
- A pending response is removed only after each valid record has been stored in
  the raw-message table, acknowledged by RabbitMQ, and checkpointed on its
  physical device.
- Writes use a temporary file, a filesystem sync, and an atomic rename.
- Correlation IDs are deterministic from the Tago device and record IDs. This
  makes raw-message insertion idempotent when recovery repeats a record.

Delivery is at least once. A process or network failure at the instant of a
RabbitMQ acknowledgement can cause a duplicate physical-timeseries message.
Consumers should use `broker_correlation_id` to deduplicate if necessary.

## Physical device identification

Each value in TAGO_DEVICE_TOKENS represents a data logger, so will represent 
a device in the physical devices table.

To avoid exposing the device API key, it must be mapped to a consistent 
value that cannot be used to derive the key and is not in any way sensitive. 
This value can be used as the IoTa physical device source id.

The Tago API device `info` endpoint provides two suitable values - `dev_eui` 
and `device_id`. `device_id` will be used for the source id.

## Implementation

### Startup

#### Physical device creation and id mapping

At startup, the poller calls the Tago `info` endpoint once for each device
token. It reads the non-secret `device_id` from that response. The token is
used only as an API credential and is never stored in the database, spool, or
logs.

The poller looks for an existing physical device with:

```python
source_name = "tago"
source_ids = {"device_id": device_id}
```

If no matching device exists, the poller creates one. Its name comes from the
Tago device name, its source ID contains only `device_id`, and its properties
contain the non-secret response from the `info` endpoint. A deterministic
creation correlation UUID is derived from `device_id`.

The poller keeps these runtime mappings:

```python
token_device_ids[token] = device_id
devices[device_id] = physical_device
device_columns[device_id] = column_definition
```

The first mapping is held only in process memory. This lets each token select
its physical device without exposing the token. The other mappings let spool
replay and message processing find the device and its device-specific CSV
layout by `device_id`.

#### Device data column definitions

The `params` API endpoint provides two important pieces of information:

- `header` gives the names of the columns of the data received via the data 
  endpoint.
- `index` gives the one-based column index for the value that represents the water 
  level being sampled. It will be an integer representing a pump number. It 
  is not yet known how to map the pump number to an actual depth such as '1 
  metre'. 

Existing devices can return this parameter as `active_index`. The poller accepts
both names.

These values can be different for each device so at each startup `params` must 
be called to get this information and associate it with the device API key 
or IoTa physical device id.

The poller trims and uses each column heading as the corresponding timeseries
name. It does not publish the first timestamp column as a reading because the
Tago record timestamp is the IoTa message timestamp. The reading selected by
`index` is named `pump_number`, regardless of its header text. If a payload has
more values than the header defines, the poller retains them as `unknown_1`,
`unknown_2`, and so on. A payload with fewer values than its header, or with an
out-of-range pump index, is quarantined.
