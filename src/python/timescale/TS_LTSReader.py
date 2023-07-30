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
    rx_channel = mq.RxChannel(BrokerConstants.LOGICAL_TIMESERIES_EXCHANGE_NAME, exchange_type=ExchangeType.fanout, queue_name='ltsreader_logical_msg_queue', on_message=on_message, routing_key='logical_timeseries')
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

    msg = json.loads(body)
    lu.cid_logger.info(f'Accepted message {msg}', extra=msg)
    
    #
    # Message processing goes here
    #
    
    json_lines = ts.parse_json(msg)
    adjust_pairings(msg.get('l_uid'), msg.get('p_uid'))

    if ts.insert_lines(json_lines) == 1:
        logging.info("Message successfully stored in database.")
    else:
        rx_channel._channel.basic_reject(delivery_tag)

    # This tells RabbitMQ the message is handled and can be deleted from the queue.    
    rx_channel._channel.basic_ack(delivery_tag)

def adjust_pairings(luid: str, puid: str):

    query = f"SELECT * FROM id_pairings WHERE l_uid = '{luid}' OR p_uid = '{puid}';"
    results = ts.send_query(query, table="id_pairings")
    
    luid_exists = False
    puid_exists = False
    
    # Analyze the results
    for row in results:
        if str(row[1]) == str(luid):
            luid_exists = True
        if str(row[2]) == str(puid):
            puid_exists = True
        if luid_exists or puid_exists:
            break

    # Perform the actions
    if luid_exists and not puid_exists:
        # Update the row to add the missing puid
        update_query = f"UPDATE id_pairings SET p_uid = '{puid}' WHERE l_uid = '{luid}';"
        ts.send_update(update_query, table="id_pairings")
        logging.info("Updated column to change p_uid")
        # Delete rows that have the same p_uid but different l_uid
        delete_query = f"DELETE FROM id_pairings WHERE p_uid = '{puid}' AND l_uid != '{luid}';"
        ts.send_update(delete_query, table="id_pairings")
        logging.info("Deleted rows with the same p_uid but different l_uid")
    elif not luid_exists and puid_exists:
        # Update the row to add the missing luid
        update_query = f"UPDATE id_pairings SET l_uid = '{luid}' WHERE p_uid = '{puid}';"
        ts.send_update(update_query, table="id_pairings")
        logging.info("Updated column to change l_uid")
        # Delete rows that have the same l_uid but different p_uid
        delete_query = f"DELETE FROM id_pairings WHERE l_uid = '{luid}' AND p_uid != '{puid}';"
        ts.send_update(delete_query, table="id_pairings")
        logging.info("Deleted rows with the same l_uid but different p_uid")
    elif not luid_exists and not puid_exists:
        # Add a new row with the given luid and puid
        insert_query = f"INSERT INTO id_pairings (l_uid, p_uid) VALUES ('{luid}', '{puid}');"
        ts.send_update(insert_query, table="id_pairings")
        logging.info("Added new ID pairing")
        
    else:
        return


if __name__ == '__main__':
    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Ctrl-C sends SIGINT, handle it the same way.
    signal.signal(signal.SIGINT, sigterm_handler)

    # Does not return until SIGTERM is received.
    asyncio.run(main())
    logging.info('Exiting.')
