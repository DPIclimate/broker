"""
This program receives logical device timeseries messages and writes them into
the volume shared with DataBolt.

The messages are written to a file in exactly the form they are received from
the logical mapper.

Intersect wants both the physical and logical device ids.

This code expects a volume shared with the DataBolt container to be mounted and
writable at /raw_data. DataBolt expects only directories under its raw_data
directory, and then a set of files with each of those directories. Each
directory is processed as a batch and a completion file written when the
batch has been successfully processed.
"""

from typing import Any

import json, logging, os, sys, time

import BrokerConstants

import util.LoggingUtil as lu

from delivery.BaseWriter import BaseWriter
from pdmodels.Models import LogicalDevice, PhysicalDevice


_raw_data_name = '/raw_data'


class DataboltWriter(BaseWriter):
    def __init__(self) -> None:
        super().__init__('databolt')

    def on_message(self, pd: PhysicalDevice, ld: LogicalDevice, msg: dict[Any], retry_count: int) -> int:
        try:
            # Only messages from Wombat or Axistech nodes should be processed for SCMN.
            if pd.source_name not in [BrokerConstants.WOMBAT, BrokerConstants.AXISTECH]:
                lu.cid_logger.info(f'Rejecting message from source {pd.source_name}', extra=msg)
                return DataboltWriter.MSG_OK

            # May as well use the message context id for the DataBolt directory and file name.
            if not os.path.isdir(_raw_data_name):
                lu.cid_logger.error(f'DataBolt {_raw_data_name} directory not found. This should be a mounted volume shared with the DataBolt container.', extra=msg)
                sys.exit(1)

            msg_uuid = msg[BrokerConstants.CORRELATION_ID_KEY]

            # Set a permissive umask to try and avoid problems with user-based file permissions between
            # different containers and the host system.
            old_umask = os.umask(0)
            try:
                os.mkdir(f'{_raw_data_name}/{msg_uuid}')
                with open(f'{_raw_data_name}/{msg_uuid}/{msg_uuid}.json', 'w') as f:
                    # The body argument is bytes, not a string. Using json.dump is a
                    # simple way to get a string written to the file.
                    json.dump(msg, f)

            except:
                lu.cid_logger.exception('Failed to write message to DataBolt directory.', extra=msg)
                return DataboltWriter.MSG_FAIL

            # Put the old umask back in case some other file operations are done in the base class.
            os.umask(old_umask)

            return DataboltWriter.MSG_OK

        except BaseException:
            lu.cid_logger.exception('Error while processing message.', extra=msg)
            return DataboltWriter.MSG_FAIL


if __name__ == '__main__':
    if not os.path.isdir(_raw_data_name):
        logging.error(f'DataBolt {_raw_data_name} directory not found. This should be a mounted volume shared with the DataBolt container.')
        sys.exit(1)

    DataboltWriter().run()
    logging.info('Exiting.')
