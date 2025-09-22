import datetime, dateutil.parser

import asyncio, json, logging, re, signal, sys, uuid
from typing import Dict, Optional

import BrokerConstants
from pdmodels.Models import PhysicalDevice
from pika.exchange_type import ExchangeType

import api.client.RabbitMQ as mq
import api.client.TTNAPI as ttn

import api.client.DAO as dao

import util.LoggingUtil as lu
import util.Timestamps as ts

std_logger = logging.getLogger(__name__)

rx_channel: mq.RxChannel = None
tx_channel: mq.TxChannel = None
mq_client: mq.RabbitMQConnection = None
finish = False






JSON_SPEC = {
  "CPL03-CB": {
    "system_vars_ts_name": "time",
    "system_vars": ["Model","IMEI","IMSI","battery","signal"],
    "timeseries_array": {
      2: {"name": "pulse1","decumulate": True},
    },
  },
  "S31x-CB": {
    "system_vars_ts_name": "time",
    "system_vars": ["Model","IMEI","IMSI","battery","signal"],
    "timeseries_array": {
      0: {"name": "temperature"},
      1: {"name": "humidity"}
    },
  }
}


def process_data(data):

  vars = JSON_SPEC[data["Model"]]
 
  dots = []

  d_ts = dateutil.parser.isoparse(data[vars["system_vars_ts_name"]])

  # devices will uplink with ts equal to epoch if it hasn't synched time yet.
  # drop messages with these timestamps. 
  if d_ts.year <= 1970:
    return([])
  
  system_dot = {BrokerConstants.TIMESTAMP_KEY: d_ts.isoformat(),BrokerConstants.TIMESERIES_KEY: []}

  # Create timeseries for system variables 
  for i in vars["system_vars"]:
    d_name = i
    d_value = data[d_name]

    d = {"name": d_name,"value": d_value}
    system_dot[BrokerConstants.TIMESERIES_KEY].append(d)


  dots.append(system_dot)


 

  last_t = None

  # Create Timeseries for buffered variaables
  # Devices support max 32 buffered data sets.
  for t in [str(i) for i in range(32,0,-1)]:
    if t in data:
      
      # timestampe is the last element of the array
      d_ts = dateutil.parser.isoparse(data[t][-1])

      # devices will uplink with ts equal to epoch if it hasn't synched time yet.
      # drop messages with these timestamps. 
      if d_ts.year <= 1970:
        continue
      
      dot = {BrokerConstants.TIMESTAMP_KEY: d_ts.isoformat(),BrokerConstants.TIMESERIES_KEY: []}

      for i in vars["timeseries_array"].keys():
        d_name  = vars["timeseries_array"][i]["name"]
        d_value = data[t][i]


        if "decumulate" in vars["timeseries_array"][i] and vars["timeseries_array"][i]["decumulate"] is True:
          if last_t is not None:
            if data[last_t][i] <= d_value:
              d_value -= data[last_t][i]


        d = {"name":d_name,"value":d_value}
        dot[BrokerConstants.TIMESERIES_KEY].append(d)

        last_t = t

      dots.append(dot)

  return(dots)






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
    global mq_client, rx_channel, tx_channel, finish

    logging.info('===============================================================')
    logging.info('               STARTING Dragino LISTENER')
    logging.info('===============================================================')

    # The default MQTT topic of YDOC devices is YDOC/<serial#> which RabbitMQ converts into a routing key of YDOC.<serial#>.
    # It seems we can use the MQTT topic wildcard of # to get all YDOC messages.
    rx_channel = mq.RxChannel('amq.topic', exchange_type=ExchangeType.topic, queue_name='dragino_listener', on_message=on_message, routing_key='dragino_up')
    tx_channel = mq.TxChannel(exchange_name=BrokerConstants.PHYSICAL_TIMESERIES_EXCHANGE_NAME, exchange_type=ExchangeType.fanout)
    mq_client = mq.RabbitMQConnection(channels=[rx_channel, tx_channel])
    asyncio.create_task(mq_client.connect())

    #while not (rx_channel.is_open and tx_channel.is_open):
    while not (rx_channel.is_open):
        await asyncio.sleep(0)

    while not finish:
        await asyncio.sleep(2)

    while not mq_client.stopped:
        await asyncio.sleep(1)


def on_message(channel, method, properties, body):
    """
    This function is called when a message arrives from RabbitMQ.
    """
    global rx_channel, tx_channel, finish

    delivery_tag = method.delivery_tag

    # If the finish flag is set, reject the message so RabbitMQ will re-queue it
    # and return early.
    if finish:
        rx_channel._channel.basic_reject(delivery_tag)
        return

    try:
        correlation_id = str(uuid.uuid4())
        lu.cid_logger.info(f'Message as received: {body}', extra={BrokerConstants.CORRELATION_ID_KEY: correlation_id})

        msg = {}
        try:
            msg = json.loads(body)
        except Exception as e:
            std_logger.info(f'JSON parsing failed, ignoring message')
            rx_channel._channel.basic_ack(delivery_tag)
            return

        # This code could put the cid into msg (and does so later) and pass msg into the lu_cid
        # logger calls. However, for consistency with other modules and to avoid problems if this code
        # is ever copy/pasted somewhere we will stick with building a msg_with_cid object and using
        # that for logging.
        msg_with_cid = {BrokerConstants.CORRELATION_ID_KEY: correlation_id, "time": msg}

        # Record the message to the all messages table before doing anything else to ensure it
        # is saved. Attempts to add duplicate messages are ignored in the DAO.
        msg_ts = dateutil.parser.isoparse(msg["time"])
        dao.add_raw_json_message(BrokerConstants.DRAGINO_JSON, msg_ts, correlation_id, msg)


        imei = msg['IMEI']
        lu.cid_logger.info(f'Accepted message from {imei}', extra=msg_with_cid)

        # Find the device using the IMEI
        find_source_id = {'IMEI': imei}
        pds = dao.get_pyhsical_devices_using_source_ids(BrokerConstants.DRAGINO_JSON, find_source_id)
        if len(pds) < 1:
            lu.cid_logger.info('Device not found, creating physical device.', extra=msg_with_cid)

            props = {
                BrokerConstants.DRAGINO_JSON: msg,
                BrokerConstants.CREATION_CORRELATION_ID_KEY: correlation_id,
                BrokerConstants.LAST_MSG: msg
            }


            source_ids = {
                'IMEI': imei
            }

            device_name = f'dragino_{imei}'
            lu.cid_logger.info(f'source_name: {BrokerConstants.DRAGINO_JSON}', extra=msg_with_cid)
            lu.cid_logger.info(f'name:        {device_name}', extra=msg_with_cid)
            lu.cid_logger.info(f'last_seen:   {msg_ts}', extra=msg_with_cid)
            lu.cid_logger.info(f'source_ids:  {source_ids}', extra=msg_with_cid)
            lu.cid_logger.info(f'properties:  {props}', extra=msg_with_cid)

            pd = PhysicalDevice(uid=1, source_name=BrokerConstants.DRAGINO_JSON, name=device_name, location=None, last_seen=msg_ts, source_ids=source_ids, properties=props)
            #pd = PhysicalDevice(source_name=BrokerConstants.DRAGINO_JSON, name=device_name, source_ids=source_ids)
            pd = dao.create_physical_device(pd)

        else:
            pd = pds[0]
            pd.last_seen = msg_ts
            pd.properties[BrokerConstants.LAST_MSG] = msg
            pd = dao.update_physical_device(pd)

        if pd is None:
            lu.cid_logger.error(f'Physical device not found, message processing ends now. {correlation_id}', extra=msg_with_cid)
            rx_channel._channel.basic_ack(delivery_tag)
            return

        lu.cid_logger.info(f'Using device id {pd.uid}', extra=msg_with_cid)


        # Process the JSON message
        dots = process_data(msg)

        # Publish each timeeseries 
        for d in dots:
          p_ts_msg = {
            BrokerConstants.CORRELATION_ID_KEY: 			correlation_id,
            BrokerConstants.PHYSICAL_DEVICE_UID_KEY: 	    pd.uid,
            BrokerConstants.TIMESTAMP_KEY: 					d[BrokerConstants.TIMESTAMP_KEY],
            BrokerConstants.TIMESERIES_KEY: 				d[BrokerConstants.TIMESERIES_KEY]
          }

          tx_channel.publish_message('physical_timeseries', p_ts_msg)

        # This tells RabbitMQ the message is handled and can be deleted from the queue.
        rx_channel._channel.basic_ack(delivery_tag)
    except Exception as e:
        std_logger.exception('Error while processing message.')
        rx_channel._channel.basic_ack(delivery_tag)


if __name__ == '__main__':
    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Does not return until SIGTERM is received.
    asyncio.run(main())
    logging.info('Exiting.')
