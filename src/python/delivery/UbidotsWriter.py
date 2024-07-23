"""
This program receives logical device timeseries messages and forwards them
on to Ubidots.
"""

from typing import Any
import dateutil.parser

import logging, math, uuid

import BrokerConstants

import api.client.Ubidots as ubidots

import api.client.DAO as dao
from delivery.BaseWriter import BaseWriter
from pdmodels.Models import LogicalDevice, PhysicalDevice
import util.LoggingUtil as lu

class UbidotsWriter(BaseWriter):
    def __init__(self, name) -> None:
        super().__init__(name)

    def on_message(self, pd: PhysicalDevice, ld: LogicalDevice, msg: dict[Any]):
        """
        This function is called when a message arrives from RabbitMQ.

        logical_timeseries has (not sure if physical dev uid is useful, discuss):
        {
            "physical_uid": 27,
            "logical_uid": 16,
            "timestamp": "2022-02-04T00:32:28.392595503Z",
            "timeseries": [
                {"name": "battery", "value": 3.5},
                {"name": "humidity", "value": 95.11},
                {"name": "temperature", "value": 4.87}
            ]
        }

        This needs to be transformed to:

        {
            'battery': {'value': 3.6, 'timestamp': 1643934748392},
            'humidity': {'value': 37.17, 'timestamp': 1643934748392},
            'temperature': {'value': 37.17, 'timestamp': 1643934748392}
        }

        So get the logical device from the db via the id in the message, and convert the iso-8601 timestamp to an epoch-style timestamp.
        """

        try:
            logging.info(f'{pd.name} / {ld.name}')

            ts = 0.0
            # TODO: Find or create a class to hide all the Python datetime processing.
            try:
                ts_float = dateutil.parser.isoparse(msg[BrokerConstants.TIMESTAMP_KEY]).timestamp()
                # datetime.timestamp() returns a float where the ms are to the right of the
                # decimal point. This should get us an integer value in ms.
                ts = math.floor(ts_float * 1000)
            except:
                lu.cid_logger.error(f'Failed to parse timestamp from message: {msg[BrokerConstants.TIMESTAMP_KEY]}', extra=msg)
                return self.MSG_FAIL

            ubidots_payload = {}
            for v in msg[BrokerConstants.TIMESERIES_KEY]:
                dot_ts = ts

                # Override the default message timestamp if one of the dot entries has its
                # own timestamp.
                if BrokerConstants.TIMESTAMP_KEY in v:
                    try:
                        dot_ts_float = dateutil.parser.isoparse(v[BrokerConstants.TIMESTAMP_KEY]).timestamp()
                        dot_ts = math.floor(dot_ts_float * 1000)
                    except:
                        # dot_ts has already been set to msg timestamp above as a default value.
                        pass

                try:
                    value = float(v['value'])
                    ubidots_payload[v['name']] = {
                        'value': value,
                        'timestamp': dot_ts,
                        'context': {
                            BrokerConstants.CORRELATION_ID_KEY: msg[BrokerConstants.CORRELATION_ID_KEY]
                        }
                    }
                except ValueError:
                    # Ubidots will not accept values that are not floats, so skip this value.
                    pass

            #
            # TODO: Add some way to abstract the source-specific details of creating the Ubidots device.
            # Anywhere this code has something like 'if pd.source_name...' it should be handled better.
            #
            # One idea is that once the broker is live (and if Ubidots supports this) we can stop the
            # logical mapper for a short while and do a bulk relabel of all Ubidots devices to some
            # scheme that does not require source-specific information, change this code, and restart
            # the logical mapper.
            #
            new_device = False
            if not 'ubidots' in ld.properties or not 'label' in ld.properties['ubidots']:
                # If the Ubidots label is not in the logical device properties, the device
                # may no exist in Ubidots yet so  we must remember to read the Ubidots
                # device back after writing the timeseries data so the device info can be
                # stored in the logical device properties.
                lu.cid_logger.info('No Ubidots label found in logical device.', extra=msg)

                new_device = True
                ld.properties['ubidots'] = {}
                # TODO: Remove the device source specific code here and always use a random
                # UUID for the Ubidots label. This cannot be done until the current TTN ubifunction
                # is switched off because the broker must be able to determine the same device label
                # used by the ubifunction when it creates Ubidots devices.
                if pd.source_name == BrokerConstants.TTN:
                    ld.properties['ubidots']['label'] = pd.source_ids['dev_eui']
                    lu.cid_logger.info(f'Using physical device eui for label: {ld.properties["ubidots"]["label"]}', extra=msg)
                elif pd.source_name == BrokerConstants.GREENBRAIN:
                    lu.cid_logger.info('Using system-station-sensor-group ids as label', extra=msg)
                    system_id = pd.source_ids['system_id']
                    station_id = pd.source_ids['station_id']
                    sensor_group_id = pd.source_ids['sensor_group_id']
                    ubi_label = f'{system_id}-{station_id}-{sensor_group_id}'
                    ld.properties['ubidots']['label'] = ubi_label
                else:
                    lu.cid_logger.info('Using a UUID as Ubidots label', extra=msg)
                    ld.properties['ubidots']['label'] = uuid.uuid4()

            #
            # So it doesn't get lost in all the surrounding code, here is where the
            # data is posted to Ubidots.
            #
            ubidots_dev_label = ld.properties['ubidots']['label']
            if not ubidots.post_device_data(ubidots_dev_label, ubidots_payload):
                # The write to Ubidots failed.
                logging.error('Delivery to Ubidots failed at API call.')
                # Make this retry later.
                return BaseWriter.MSG_FAIL

            if new_device:
                # Update the Ubidots device with info from the source device and/or the
                # broker.
                lu.cid_logger.info('Updating Ubidots device with information from source device.', extra=msg)
                patch_obj = {'name': ld.name}
                patch_obj['properties'] = {}

                # Prefer the logical device location, fall back to the mapped physical device
                # location, if any.
                loc = ld.location if ld.location is not None else pd.location
                if loc is not None:
                    patch_obj['properties'] |= {'_location_type': 'manual', '_location_fixed': {'lat': loc.lat, 'lng': loc.long}}

                # We could include the correlation id of the message that caused the device to be created
                # in the same format as the QR code id below, but I'm not sure that's useful and it might clutter
                # up the Ubidots UI.

                if pd.source_name == BrokerConstants.TTN:
                    if BrokerConstants.TTN in pd.properties:
                        ttn_props = pd.properties[BrokerConstants.TTN]
                        if 'description' in ttn_props:
                            patch_obj['description'] = ttn_props['description']

                        if 'attributes' in ttn_props and 'uid' in ttn_props['attributes']:
                            cfg = {'dpi-uid': {'text': 'DPI UID', 'type': 'text', 'description': 'The uid from the DPI QR code used to activate the device.'}}
                            patch_obj['properties'] |= {'_config': cfg, 'dpi-uid': ttn_props['attributes']['uid']}

                    # TODO: What about Green Brain devices?

                ubidots.update_device(ubidots_dev_label, patch_obj)

                # Update the newly created logical device properties with the information
                # returned from Ubidots, but nothing else. We don't want to overwite the
                # last_seen value because that should be set to the timestamp from the
                # message, which was done in the mapper process.
                lu.cid_logger.info('Updating logical device properties from Ubidots.', extra=msg)
                ud = ubidots.get_device(ubidots_dev_label)
                if ud is not None:
                    ld.properties['ubidots'] = ud.properties['ubidots']
                    dao.update_logical_device(ld)

            return self.MSG_OK

        except BaseException:
            logging.exception('Error while processing message.')
            return self.MSG_FAIL


if __name__ == '__main__':
    UbidotsWriter('ubidots').run()
    logging.info('Exiting.')
