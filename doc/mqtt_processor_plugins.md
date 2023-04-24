# Introduction
On startup the mqtt front end processor searches for any plugins inside its plugins directory.  
These plugins are actually just Python Modules.

## Module Properties

Each module must have the following properties defined.

| Property name | Type | Description |
|:---:|:---:|:---:|
| TOPIC | <kbd>string</kbd> | The MQTT Topic that the processor will subscribe to. |
| on_message | <kbd>function</kbd> | A function which will be executed whenever a message is received to the subscribed topic. |

### `on_message` parameters

The `on_message` function will be passed the following parameters.

| Parameter name | Type | Description |
|:---:|:---:|:---:|
| message | <kbd>string</kbd> | The MQTT message received as a string. |
| properties | <kbd>object</kbd> | An object containing the original pikamq callback parameters. `channel`, `method`, `properties`, `body` |

### `on_message` return

The `on_message` function should return the processed message or throw an exception if there is an issue.