"""
This program receives logical device timeseries messages and logs
them as a test of having multiple queues attached to the logical_timeseries exchange.

It can be used as a template for any program that wants to read from the logical
timeseries exchange. To do that, change the queue name to something unique.
"""

import asyncio, json, logging, signal

from pika.exchange_type import ExchangeType
import api.client.RabbitMQ as mq
import BrokerConstants
import util.LoggingUtil as lu
import timescale.Timescale as ts

rx_channel = None
mq_client = None
finish = False


def sigterm_handler(sig_no, stack_frame) -> None:
    """
    Handle SIGTERM from docker by closing the mq and db connections and setting a
    flag to tell the main loop to exit.
    """
    global finish, mq_client

    logging.info(f'Caught signal {signal.strsignal(sig_no)}, setting finish to True')
    finish = True
    mq_client.stop()


async def main():
    """
    Initiate the connection to RabbitMQ and then idle until asked to stop.

    Because the messages from RabbitMQ arrive via async processing this function
    has nothing to do after starting connection.
    """
    global mq_client, rx_channel, finish

    logging.info('===============================================================')
    logging.info('               STARTING LOGICAL_TIMESERIES TEST READER')
    logging.info('===============================================================')

    # The routing key is ignored by fanout exchanges so it does not need to be a constant.
    # Change the queue name. This code should change to use a server generated queue name.
    rx_channel = mq.RxChannel(
        "TEST_BULK", 
        exchange_type=ExchangeType.fanout, 
        queue_name='bulky_ts_queue', 
        on_message=on_message, 
        routing_key='bulky_timeseries'
    )
    mq_client = mq.RabbitMQConnection(channels=[rx_channel])
    asyncio.create_task(mq_client.connect())

    while not rx_channel.is_open:
        await asyncio.sleep(0)

    while not finish:
        await asyncio.sleep(2)

    while not mq_client.stopped:
        await asyncio.sleep(1)


def on_message(channel, method, properties, body):
    """
    This function is called when a message arrives from RabbitMQ.
    """

    global rx_channel, finish

    delivery_tag = method.delivery_tag

    # If the finish flag is set, reject the message so RabbitMQ will re-queue it
    # and return early.
    if finish:
        rx_channel._channel.basic_reject(delivery_tag)
        return

    msgs = json.loads(body)
    lu.cid_logger.info(f'Accepted message {msgs}', extra=msgs)
    
    #
    # Message processing goes here
    #


    parsed_msgs = []
    try:
        for line in msgs["data"]:
            #print(f"Processing line: {line}")
            parsed_msg = ts.parse_json(line)
            parsed_msgs.extend(parsed_msg)  # Extend the list instead of appending
        ts.insert_lines_bulk(parsed_msgs)        
    except Exception as e:
        lu.cid_logger.error(f'Unable to process LTS message: {e}')
        rx_channel.channel.basic_reject(delivery_tag)
    
    # try:
    #     for msg in msgs["data"]:
    #         parsed_msgs.append(ts.parse_json(msg))
    #     ts.insert_lines_bulk(parsed_msgs)
    # except Exception as e:
    #     lu.cid_logger.error(f'Unable to process LTS message: {e}')
    #     rx_channel.channel.basic_reject(delivery_tag)
    #     return

    # This tells RabbitMQ the message is handled and can be deleted from the queue.    
    rx_channel._channel.basic_ack(delivery_tag)


if __name__ == '__main__':
    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Ctrl-C sends SIGINT, handle it the same way.
    signal.signal(signal.SIGINT, sigterm_handler)

    # Does not return until SIGTERM is received.
    asyncio.run(main())
    logging.info('Exiting.')