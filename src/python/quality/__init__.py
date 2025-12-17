import datetime as dt
import dateutil.tz as dutz
import os
import sqlalchemy as sqla
import sqlalchemy.engine


_report_str = '''---
title: SCMN Daily Quality Checks
maxwidth: "36em"
lang: en_AU
header-includes: |
  <style>
  th:first-child {text-align: left;}
  </style>
---
\n\n'''

# FIXME: Passing immutable strings down through the visitor processing did not give the results
# FIXME: I hoped for. A short-term fix is to write to this global var!
markdown = ''

class ReportFragment:
    """
    To avoid writing empty sections of the report, use a tree of report fragments. Any fragment that does not
    have any children and is not marked as always emit will not appear in the output.
    """
    def __init__(self, parent, title: str = '', text: str = '', always_emit = False) -> None:
        self.parent = parent
        self.level = self.parent.level + 1 if self.parent is not None else 1
        self.title = title
        self.text = text
        self.always_emit = always_emit
        self.children = []
        if parent is not None:
            self.parent.children.append(self)

    def visit(self, report: str) -> None:
        global markdown

        if (not self.always_emit) and len(self.children) < 1:
            return

        if self.title is not None and len(self.title) > 0:
            markdown += f'{'#' * self.level} {self.title}\n\n'

        if self.text is not None and len(self.text) > 0:
            markdown += self.text + '\n\n'

        for child in self.children:
            child.visit(report)

    def __str__(self) -> str:
        s = f'[Level: {self.level}, always_emit: {self.always_emit}] {self.title}\n{self.text}\n\n'
        for child in self.children:
            s += child.__str__()

        return s


location_dev_name_qry = 'select uid, name, last_seen from logical_devices'

# This map contains logical_uid -> (device_name, last_seen), ATM filled in in daily.py
devs = {}

# These are for use by the check drivers and plugins.
_ts_conn_uri = sqlalchemy.engine.URL.create(
    drivername='postgresql',
    username=os.environ["TSUSER"],
    password=os.environ["TSPASSWORD"],
    host=os.environ["TSHOST"],
    port=os.environ["TSPORT"],
    database=os.environ["TSDATABASE"])

ts_engine = sqla.create_engine(_ts_conn_uri, pool_size=2, max_overflow=5)
""" Use this to get connections to the SCMN TimescaleDB database."""

_iota_conn_uri = sqlalchemy.engine.URL.create(
    drivername='postgresql',
    username=os.environ["PGUSER"],
    password=os.environ["PGPASSWORD"],
    host=os.environ["PGHOST"],
    port=os.environ["PGPORT"],
    database=os.environ["PGDATABASE"])

iota_engine = sqla.create_engine(_iota_conn_uri, pool_size=2, max_overflow=5)
""" Use this to get connections to the IoTa database."""


report_date = dt.datetime.now(tz=dutz.gettz(os.getenv('TZ', 'UTC')))
report_date = report_date - dt.timedelta(days=1)

# No title on the report root because pandoc needs it in the YAML init block of the markdown.
report_root = ReportFragment(None, '', _report_str, True)

# Shift the report root as seen by the rest of the checking code down to the per-day level.
report_root = ReportFragment(report_root, title=report_date.strftime('%A %d %B %Y'), always_emit=True)

emit_report = False
