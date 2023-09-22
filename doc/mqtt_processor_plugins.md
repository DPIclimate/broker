# Introduction
On startup the mqtt front end processor searches for any plugins inside its plugins directory.  
These plugins are actually just Python Modules.

## Module Properties

Each module must have the following properties defined.

| Property name | Type | Description |
|:---:|:---:|:---:|
| TOPICS | <kbd>array</kbd><kbd>string</kbd> | An array of strings, each string being an MQTT topic that the processor will subscribe to. |
| on_message | <kbd>function</kbd> | A function which will be executed whenever a message is received to the subscribed topic. |

### `on_message` parameters

The `on_message` function will be passed the following parameters.

| Parameter name | Type | Description |
|:---:|:---:|:---:|
| message | <kbd>string</kbd> | The MQTT message received as a string. |
| properties | <kbd>dictionary</kbd> | An dictionary containing the original pikamq callback parameters. `channel`, `method`, `properties`, `body` |

### `on_message` return

The `on_message` function should return a dictionary formatted as below.  
If the raw message cannot be processed, an exception should be raised.

| Key | Type | Description |
|:---:|:---:|:---:|
| messages | <kbd>array</kbd> | An array of processed messaged to be sent to the Physical Timeseries. |
| errors | <kbd>array</kbd> | An array of strings or exceptions to be logged |
