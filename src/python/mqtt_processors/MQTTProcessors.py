import datetime, dateutil.parser

import asyncio, json, logging, pkgutil, re, signal, sys, uuid
from typing import Dict, Optional

import BrokerConstants
from pdmodels.Models import PhysicalDevice
from pika.exchange_type import ExchangeType

import api.client.RabbitMQ as mq
import api.client.TTNAPI as ttn

import api.client.DAO as dao

import util.LoggingUtil as lu
import util.Timestamps as ts

import plugins

std_logger = logging.getLogger(__name__)

tx_channel: mq.TxChannel = None
mq_client: mq.RabbitMQConnection = None
finish = False

plugin_modules = []

def sigterm_handler(sig_no, stack_frame) -> None:
    """
    Handle SIGTERM from docker by closing the mq and db connections and setting a
    flag to tell the main loop to exit.
    """
    global finish, mq_client

    logging.debug(f'{signal.strsignal(sig_no)}, setting finish to True')
    finish = True
    dao.stop()
    mq_client.stop()


async def main():
    """
    Initiate the connection to RabbitMQ and then idle until asked to stop.

    Because the messages from RabbitMQ arrive via async processing this function
    has nothing to do after starting connection.

    It would be good to find a better way to do nothing than the current loop.
    """
    global mq_client, tx_channel, finish, plugin_modules

    logging.info('===============================================================')
    logging.info('               STARTING MQTT Processor LISTENER')
    logging.info('===============================================================')
    
    # Load each plugin module
    package = plugins
    prefix = package.__name__ + "."
    for importer, modname, ispkg in pkgutil.iter_modules(package.__path__, prefix):
        print("Found submodule %s (is a package: %s)" % (modname, ispkg))
        module = __import__(modname, fromlist="dummy")
        std_logger.info("Imported Plugin", module)
        plugin_modules.append(module)
    
    # Subscribe each plugin to its topic
    rx_channels = []
    for plugin in plugin_modules:
        try:
            rx_channel = mq.RxChannel('amq.topic', exchange_type=ExchangeType.topic, queue_name=plugin.__name__, on_message=plugin.on_message, routing_key=plugin.TOPIC)
            rx_channels.append(rx_channel)
        except Exception as e:
            std_logger.error("Failed to subscribe plugin to MQTT topic", e)
    
    # Set up the transmit channel and finally create the client
    tx_channel = mq.TxChannel(exchange_name=BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME, exchange_type=ExchangeType.fanout)
    mq_client = mq.RabbitMQConnection(channels=rx_channels + tx_channel)
    asyncio.create_task(mq_client.connect())

    # TODO - Figure out a better way to do this
    #while not (rx_channel.is_open and tx_channel.is_open):
    #while not (rx_channel.is_open):
        #await asyncio.sleep(0)

    while not finish:
        await asyncio.sleep(2)

    while not mq_client.stopped:
        await asyncio.sleep(1)


def on_message(channel, method, properties, body):
    """
    This function is called when a message arrives from RabbitMQ.
    """
    global tx_channel, finish

    delivery_tag = method.delivery_tag

    # If the finish flag is set, reject the message so RabbitMQ will re-queue it
    # and return early.
    if finish:
        channel.basic_reject(delivery_tag)
        return

    try:
        # process message
        logging.info("Message Received")
    except Exception as e:
        std_logger.exception('Error while processing message.')
        channel.basic_ack(delivery_tag)


if __name__ == '__main__':
    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Does not return until SIGTERM is received.
    asyncio.run(main())
    logging.info('Exiting.')
