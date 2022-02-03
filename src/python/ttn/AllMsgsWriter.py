#
# TODO:
# 
# Test the behaviour when the DB is not available or fails.
# Ensure RabbitMQ messages are not ack'd so they can be re-delivered. Figure out how to get
# RabbitMQ to re-deliver them.
#

import datetime
import dateutil.parser

import asyncio, json, logging, math, os, signal

from pdmodels.Models import PhysicalDevice, Location
import api.client.RabbitMQ as mq
import api.client.TTNAPI as ttn

import db.DAO as dao

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
logger = logging.getLogger('AllMsgsWriter') # Shows as __main__ if __name__ is used.

mq_client = None
finish = False


def bind_ok():
    """
    This callback means the connection to the message queue is ready to use.
    """
    global mq_client
    mq_client.start_listening('ttn_raw')


def sigterm_handler(sig_no, stack_frame) -> None:
    """
    Handle SIGTERM from docker by closing the mq and db connections and setting a
    flag to tell the main loop to exit.
    """
    global finish

    logger.info(f'{signal.strsignal(sig_no)}, setting finish to True')
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
    global mq_client, finish

    logger.info('===============================================================')
    logger.info('               STARTING TTN ALLMSGSWRITER')
    logger.info('===============================================================')

    mq_client = mq.RabbitMQClient(on_bind_ok=bind_ok, on_message=on_message)
    asyncio.create_task(mq_client.connect())

    while not finish:
        await asyncio.sleep(2)

    while not mq_client.stopped:
        await asyncio.sleep(1)


def on_message(channel, method, properties, body):
    """
    This function is called when a message arrives from RabbitMQ.
    """
    global mq_client, finish

    # If the finish flag is set, exit without doing anything. Do not
    # ack the message so it stays on the queue.
    if finish:
        return

    delivery_tag = method.delivery_tag

    try:
        msg = json.loads(body)
        last_seen = None
        # We should always get a value in the message for this, but default to 'now' just in case.
        received_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if 'received_at' in msg:
            received_at = msg['received_at']

        last_seen = dateutil.parser.isoparse(received_at)

        app_id = msg['end_device_ids']['application_ids']['application_id']
        dev_id = msg['end_device_ids']['device_id']
        dev_eui = msg['end_device_ids']['dev_eui'].lower()

        # Record the message to the all messages table before doing anything else to ensure it
        # is saved.
        dao.add_ttn_message(app_id, dev_id, dev_eui, last_seen, msg)

        pd = None
        devs = dao.get_physical_devices(query_args={'prop_name': ['app_id', 'dev_id'], 'prop_value': [app_id, dev_id]})
        if len(devs) < 1:
            logger.info('Device not found, creating physical device.')
            ttn_dev = ttn.get_device_details(app_id, dev_id)
            print(f'Device info from TTN: {ttn_dev}')

            dev_name = ttn_dev['name'] if 'name' in ttn_dev else dev_id
            dev_loc = Location.from_ttn_device(ttn_dev)
            props = {'app_id': app_id, 'dev_id': dev_id }

            pd = PhysicalDevice(source_name='ttn', name=dev_name, location=dev_loc, last_seen=last_seen, properties=props)
            pd = dao.create_physical_device(pd)
        elif len(devs) == 1:
            pd = devs[0]
            logger.info(f'Updating last_seen for device {pd.name}')

            if last_seen != None:
                pd.last_seen = last_seen
                pd = dao.update_physical_device(pd.uid, pd)
        else:
            # Could use the device with the lowest uid because it would have been created first and
            # later ones are erroneous dupes.
            logger.warning(f'Found {len(devs)} devices: {devs}')

        if pd is not None:
            # TODO: Run the decoder here, or move all this to another process reading from another queue.
            uplink_message = msg['uplink_message']
            if uplink_message is not None:
                decoded_payload = uplink_message['decoded_payload']
                if decoded_payload is not None:
                    ts_vars = []
                    for k, v in decoded_payload.items():
                        ts_vars.append({k: v})
                    
                    """
                    physical_timeseries has:
                    {'physical_uid': physical_dev_uid, , 'timestamp': iso_8601_timestamp, 'timeseries': [ {'ts_key': value}, ...]}
                    """
                    p_ts_msg = {'physical_uid': pd.uid, 'timestamp': received_at, 'timeseries': ts_vars}

                    # Should the code try and remember the message until it is delivered to the queue?
                    # I think that means we need to hold off the ack in this method and only ack the message
                    # we got from ttn_raw when we get confirmation from the server that it has saved the message
                    # written to the physical_timeseries queue.
                    msg_id = mq_client.publish_message('physical_timeseries', p_ts_msg)

        # This tells RabbitMQ the message is handled and can be deleted from the queue.    
        mq_client.ack(delivery_tag)

    except BaseException as e:
        print(f'Device not found, creating physical device. Caught: {e}')



if __name__ == '__main__':
    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Does not return until SIGTERM is received.
    asyncio.run(main())
    logger.info('Exiting.')
