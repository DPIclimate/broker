import logging
import sqlalchemy as sqla
import quality


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_daily_msg_count_qry = """
with daily_msg_count as (
select logical_uid, COUNT(*) as daily_count
from physical_timeseries
where
	ts >= :start
	and ts < :start + interval '1 d'
	and logical_uid is not null
group by logical_uid order by logical_uid)

select * from daily_msg_count where daily_count <> 96;
"""

def run_check() -> None:
    with quality.iota_engine.connect() as conn:
        dev_name_results = conn.execute(sqla.text(_daily_msg_count_qry), parameters={'start': quality.report_date})
        if dev_name_results.rowcount > 0:
            # This is a local instance of emit_report, used to decide whether to set the instance in the quality namespace later.
            emit_report = False

            text = '| Location | Daily message count |\n'
            text += '|---|---:|\n'
            for locn, msg_count in dev_name_results:
                # FIXME: Externalise the conditions?

                # Skip Axistech devices for this part of the report, they do not have a regular
                # daily message count. Ian suggests >= 80 for Axistech is ok.
                if (locn == 372 or locn == 373) and msg_count >= 75:
                    continue

                if (locn != 372 and locn != 373) and (msg_count > 92 and msg_count < 96):
                    # Between 92 and 96 messages/day is acceptable for a Wombat.
                    continue

                text += f'| {locn} &mdash; {quality.devs[locn][0]} | {msg_count} |\n'
                emit_report = True

            if emit_report:
                text = '\n> Nodes that did not send the expected number of messages.\n\n' + text
                quality.ReportFragment(quality.report_root, title='Irregular Locations', text=text, always_emit=True)
                quality.emit_report = True
