import datetime, dateutil.parser, time

import asyncio, json, logging, re, signal, sys, uuid
from typing import Dict, Optional

import BrokerConstants
from pdmodels.Models import PhysicalDevice
from pika.exchange_type import ExchangeType

import api.client.RabbitMQ as mq
#import api.client.TTNAPI as ttn

import api.client.DAO as dao

import util.LoggingUtil as lu
import util.Timestamps as ts


from milesightLufft.MilesightUc300Ucp import MilesightUc300Ucp
#import pprint



rx_channel: mq.RxChannel = None
tx_channel: mq.TxChannel = None
mq_client: mq.RabbitMQConnection = None
finish = False

def sigterm_handler(sig_no, stack_frame) -> None:
    """
    Handle SIGTERM from docker by closing the mq and db connections and setting a
    flag to tell the main loop to exit.
    """
    global finish, mq_client

    logging.debug(f'{signal.strsignal(sig_no)}, setting finish to True')
    finish = True
    #dao.stop()
    mq_client.stop()


def signed(u):
  """
  Convert intt16 to signed.
  """
  s = u if u < (1 << 16-1) else u - (1 <<16)
  return(s)


async def main():
    """
    Initiate the connection to RabbitMQ and then idle until asked to stop.

    Because the messages from RabbitMQ arrive via async processing this function
    has nothing to do after starting connection.

    It would be good to find a better way to do nothing than the current loop.
    """
    global mq_client, rx_channel, tx_channel, finish

    logging.info('===============================================================')
    logging.info('               STARTING MILESIGHT LISTENER')
    logging.info('===============================================================')


    # Note the MQTT topic hierarchy separator / is not used, but . is used instead.
    # It seems we can use the MQTT topic wildcard of # to get all messages.
    rx_channel = mq.RxChannel('amq.topic', exchange_type=ExchangeType.topic, queue_name='milesight-lufft_listener', on_message=on_message, routing_key='uc.#.ucp.14.status')
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


def process_message(msg_with_cid: Dict) -> Dict[str, Dict]:
    msg = msg_with_cid[BrokerConstants.RAW_MESSAGE_KEY]


    return devices


def decode_message(body):

  # Decode the message using the kaitai produced decoder.
  # * This converts the message to an object with various properties containing 
  #   sensor data.  
  # * These properties are named after the names of the inputs on the UC300 device.
  decodedMsg = MilesightUc300Ucp.from_bytes(body)



  # An uplink from the UC300 may include multiple UCP messages.
  # We are only interested in processing "Regular Reports" and "Attribute Reports"
  # Refer to the Milesight UC300 communications guide for details.  
  outputs = []

  for msg in decodedMsg.reports:

    output = {}

    if msg.data_type==244:
      # Regular Report containing sensor data

      # Assign names to data points and process returned values as needed.
      output["timestamp"] =       msg.data.timestamp
      output["signalStrength"] =  signed(msg.data.signal_strength*2+-113)
      output["airTempAVG"] =      signed(msg.data.modbus_inputs[0].values[0]) * 0.1
      output["relHumidityAVG"] =  signed(msg.data.modbus_inputs[1].values[0]) * 0.1
      output["windDirACT"] =      signed(msg.data.modbus_inputs[2].values[0]) * 0.1
      output["compass"] =         signed(msg.data.modbus_inputs[3].values[0]) * 0.1
      output["precipType"] =             msg.data.modbus_inputs[3].values[1]
      output["dewPointAVG"] =     signed(msg.data.modbus_inputs[4].values[0]) * 0.1
      output["windChill"] =       signed(msg.data.modbus_inputs[4].values[1]) * 0.1
      output["windQuality"] =            msg.data.modbus_inputs[5].values[0]
      output["windSpeedMAX"] =    signed(msg.data.modbus_inputs[6].values[0]) * 0.1
      output["windSpeedAVG"] =    signed(msg.data.modbus_inputs[6].values[1]) * 0.1
      output["precipABS"] =              msg.data.modbus_inputs[7].values[0]  * 0.01
      # output["precipAVG"] =             msg.data.modbus_inputs[7].values[1] * 0.01
      # output["precipIntensity"] =       msg.data.modbus_inputs[7].values[2] * 0.01
      output["airPressureAVG"] =  signed(msg.data.modbus_inputs[8].values[0]) * 0.1
      output["windSpeedSD"] =     signed(msg.data.modbus_inputs[9].values[0]) * 0.01
      output["windDirSD"] =       signed(msg.data.modbus_inputs[10].values[0])* 0.01
      output["wetBulb"] =         signed(msg.data.modbus_inputs[10].values[1])* 0.1
      output["airDensityACT"] =   signed(msg.data.modbus_inputs[11].values[0])* 0.001
      output["heatTempWind"] =    signed(msg.data.modbus_inputs[12].values[0])* 0.1
      output["heatTempR2S"] =     signed(msg.data.modbus_inputs[12].values[1])* 0.1

      outputs.append(output)

    elif msg.data_type==243:
      # Attribute report containing UC300 device details (sent on power-on or reboot)
      # Message does not contain timestamp, so just use now as approximate timestamp.
      # There data contained in this message device is not sensor data, it's data
      # about the UC300 RTU
      output["timestamp"]        = int(time.time())
      output["serialNumber"]     = msg.data.serial_number
      output["ucpVersion"]  	   = msg.data.ucp_version
      output["hardwareVersion"]  = msg.data.hardware_version
      output["softwareVersion"]  = msg.data.software_version
      output["imei"]             = msg.data.imei
      output["imsi"]             = msg.data.imsi
      output["iccid"]            = msg.data.iccid

      outputs.append(output)

    else:
      lu.cid_logger.info(f'Skipping message with unsupported data type: {msg.data_type}', extra={BrokerConstants.CORRELATION_ID_KEY: correlation_id})
      continue;
 

  return(outputs)


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

        # Convert message body (bytes object) to hex string. The "raw" messages are stored as hex strings.
        # NOTE: The decioder operates on bytes objects.
        # The hex string can be converted back to byte object via "bytes.fromhex(bodyHexStr)". 
        bodyHexStr = body.hex()

        msg_with_cid = {BrokerConstants.CORRELATION_ID_KEY: correlation_id, BrokerConstants.RAW_MESSAGE_KEY: bodyHexStr}

        # Record the message to the all messages table before doing anything else to ensure it
        # is saved. Attempts to add duplicate messages are ignored in the DAO.
        # The 'now' timestamp is used so the message can be recorded ASAP and before any processing
        # that might fail or cause the message to be ignored is performed.
        dao.add_raw_text_message(BrokerConstants.MILESIGHTUC300, ts.now_utc(), correlation_id, bodyHexStr)


        # Obtain the Milesight SN from the mqtt topic (AMQP routing_key).Note: the Milesight UC300 does not 
        # include a serial number within the message body.
        serial_no = re.match('uc\.(.*)\.ucp\.14\.status',method.routing_key).groups()[0]
        dev_name = f"milesight-{serial_no}" 

        lu.cid_logger.info(f'Received message from {dev_name}', extra=msg_with_cid)

        printed_msg = False

        # Decode and process the message.
        decodedMsgs = decode_message(body)

        # Determine the last seen timestamp. If the message contains interesting data along with a timestamp, then
        # use that timestamp. If not, use "now" as the timestamp.
        last_seen = ts.now_utc()

        if len(decodedMsgs) == 0:       
          lu.cid_logger.info(f'Decoded message from {dev_name} containing no data of interest.', extra=msg_with_cid)
        else:
          lu.cid_logger.info(f'Decoded message from {dev_name} containing {len(decodedMsgs)} data sets.', extra=msg_with_cid)
          if 'timestamp' in decodedMsgs[0]:
            # Create the timestamp from milliseconds provided by the RTU
            last_seen = datetime.datetime.fromtimestamp(decodedMsgs[0]['timestamp'])

      
        # Find the physical device and update 'last_seen' and 'last_msg'. If an existing physical_device is not found,
        # create one.
        pds = dao.get_physical_devices({"name": dev_name})
        if len(pds) < 1:
          if not printed_msg:
            printed_msg = True
            lu.cid_logger.info(f'Message from a new device.', extra=msg_with_cid)
            lu.cid_logger.info(body, extra=msg_with_cid)

          lu.cid_logger.info('Device not found, creating physical device.', extra=msg_with_cid)

          props = {
            BrokerConstants.MILESIGHTUC300: decodedMsgs,
            BrokerConstants.CREATION_CORRELATION_ID_KEY: correlation_id,
            BrokerConstants.LAST_MSG: decodedMsgs
          }

          pd = PhysicalDevice(source_name=BrokerConstants.MILESIGHTUC300, name=dev_name, location=None, last_seen=last_seen, source_ids={"id": dev_name}, properties=props)
          pd = dao.create_physical_device(pd)
        else:

          lu.cid_logger.info('Existing device found, updating physical device.', extra=msg_with_cid)

          pd = pds[0]
          if last_seen is not None:
            pd.last_seen = last_seen
            pd.properties[BrokerConstants.LAST_MSG] = decodedMsgs
            pd = dao.update_physical_device(pd)

          

       
        # Convert messages to correct format for publishing to the mid-tier (Logical Mapper).
        # If the incomming message contained multiple data sets, then publish multiple
        # messages to the mid-tier.
        for m in decodedMsgs:
          p_ts_msg = {
            BrokerConstants.CORRELATION_ID_KEY: correlation_id,
            BrokerConstants.PHYSICAL_DEVICE_UID_KEY: pd.uid,
            BrokerConstants.TIMESTAMP_KEY: m['timestamp'],
            BrokerConstants.TIMESERIES_KEY: m
          }
          #pprint.pprint(decodedMsgs,indent=2)

          lu.cid_logger.debug(f'Publishing message: {p_ts_msg}', extra=msg_with_cid)
          tx_channel.publish_message('physical_timeseries', p_ts_msg)


        # This tells RabbitMQ the message is handled and can be deleted from the queue.    
        rx_channel._channel.basic_ack(delivery_tag)
        lu.cid_logger.debug('Acking message from RabbitMQ.', extra=msg_with_cid)


    except Exception as e:
        logging.error(body)
        logging.exception('Error while processing message.')
        rx_channel._channel.basic_ack(delivery_tag)



if __name__ == '__main__':

    # Docker sends SIGTERM to tell the process the container is stopping so set
    # a handler to catch the signal and initiate an orderly shutdown.
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Does not return until SIGTERM is received.
    asyncio.run(main())
    logging.info('Exiting.')
