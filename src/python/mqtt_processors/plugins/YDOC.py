# The default MQTT topic of YDOC devices is YDOC/<serial#> which RabbitMQ converts into a routing key of YDOC.<serial#>.
# It seems we can use the MQTT topic wildcard of # to get all YDOC messages. 'YDOC.#'
TOPIC = 'YDOC.#'

def on_message(message, properties):
    return
