import logging
import quality

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def run_check() -> None:
    rf = quality.ReportFragment(quality.report_root, title='Late Locations', always_emit=True)

    # This is a local instance of emit_report, used to decide whether to set the instance in the quality namespace later.
    emit_report = False

    text = '\n> Nodes not seen within the last 24 hours.\n\n'
    text += '| Location | Last seen |\n'
    text += '|---|---:|\n'

    for locn, dev in quality.devs.items():
        if dev[1] is None:
            logger.warning(f' No last seen date {locn}, {dev}')
            continue

        tdelta = quality.report_date - dev[1]
        if tdelta.days > 0:
            logger.info(f' {dev}: {tdelta} days ago')
            text += f'| {locn} &mdash; {quality.devs[locn][0]} | {tdelta.days} |\n'
            emit_report = True

    if emit_report == True:
        rf.text = text
        quality.emit_report = True
