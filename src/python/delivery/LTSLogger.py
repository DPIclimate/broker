"""
A test delivery service. Simply logs the messages it receives.
"""

from typing import Any

import logging

import util.LoggingUtil as lu

from delivery.BaseWriter import BaseWriter
from pdmodels.Models import LogicalDevice, PhysicalDevice

class LTSLogger(BaseWriter):
    def __init__(self) -> None:
        super().__init__('ltslogger')

    def on_message(self, pd: PhysicalDevice, ld: LogicalDevice, msg: dict[Any], retry_count: int) -> int:
        try:
            lu.cid_logger.info(f'{msg}, retry_count = {retry_count}', extra=msg)
            return LTSLogger.MSG_OK

        except BaseException:
            logging.exception('Error while processing message.')
            return LTSLogger.MSG_FAIL


if __name__ == '__main__':
    LTSLogger().run()
    logging.info('Exiting.')
