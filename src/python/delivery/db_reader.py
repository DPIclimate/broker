#!/usr/bin/env python3
"""Reusable synchronous database reader base class for delivery modules."""

import argparse
import datetime
import json
import logging
import signal
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cache
from typing import Any, Callable, List, Optional, Tuple

try:
    from psycopg2.pool import SimpleConnectionPool
except ModuleNotFoundError as exc:
    raise SystemExit("Missing dependency: psycopg2. Install with: pip install psycopg2") from exc


logging.basicConfig(level=logging.INFO, format="%(asctime)s|%(levelname)s|%(message)s")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LogicalTimeseriesRow:
    """Database row model for logical_timeseries delivery processing."""

    uid: int
    physical_uid: int
    logical_uid: int
    ts: datetime.datetime
    received_at: datetime.datetime
    json_msg: Any


class DeliveryDbReader(ABC):
    """Base class for DB-backed delivery implementations.

    This class owns all Postgres interaction and run-loop orchestration.
    """

    def __init__(self, poll_interval_seconds: float = 300.0):
        """Initialise database polling state.

        Args:
            poll_interval_seconds: Polling interval for live DB mode.

        Returns:
            None.
        """
        self.poll_interval_seconds = poll_interval_seconds
        self._last_uid: int = 0
        self._checkpoint_initialised = False

    _db_pool: Optional[SimpleConnectionPool] = None

    def _parse_iso_date(self, value: str) -> datetime.date:
        """argparse date parser for YYYY-MM-DD.

        Args:
            value: Date text.

        Returns:
            Parsed date.

        Raises:
            argparse.ArgumentTypeError: If format is invalid.
        """
        try:
            return datetime.date.fromisoformat(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Invalid date '{value}'. Use YYYY-MM-DD.") from exc

    def build_arg_parser(self) -> argparse.ArgumentParser:
        """Build parser with shared args and subclass extension hook.

        Args:
            None.

        Returns:
            Configured parser.
        """
        parser = argparse.ArgumentParser(description=self.parser_description())
        self.add_subclass_args(parser)
        parser.add_argument(
            "--from-date",
            type=self._parse_iso_date,
            help="Process logical_timeseries rows from this date (YYYY-MM-DD).",
        )
        parser.add_argument(
            "--to-date",
            type=self._parse_iso_date,
            help="Process logical_timeseries rows through this date (YYYY-MM-DD).",
        )
        return parser

    def validate_date_args(
        self,
        from_date: Optional[datetime.date],
        to_date: Optional[datetime.date],
    ) -> Tuple[Optional[datetime.date], Optional[datetime.date]]:
        """Validate and normalize replay date arguments.

        Args:
            from_date: Optional replay start date.
            to_date: Optional replay end date.

        Returns:
            Tuple of normalized `(from_date, to_date)`.

        Raises:
            ValueError: If date arguments are inconsistent.
        """
        if to_date is not None and from_date is None:
            raise ValueError("--to-date requires --from-date.")
        if from_date is not None and to_date is None:
            to_date = datetime.date.today()
        if from_date is not None and to_date is not None and to_date < from_date:
            raise ValueError("--to-date must be on or after --from-date.")
        return from_date, to_date

    def fetch_rows_in_date_range(
        self,
        from_date: datetime.date,
        to_date: datetime.date,
    ) -> List[LogicalTimeseriesRow]:
        """Fetch mapped rows between two local calendar dates.

        Args:
            from_date: Inclusive start date.
            to_date: Inclusive end date.

        Returns:
            Rows ordered by `(ts, uid)`.
        """
        local_tz = datetime.datetime.now().astimezone().tzinfo
        if local_tz is None:
            local_tz = datetime.timezone.utc

        from_start = datetime.datetime.combine(from_date, datetime.time.min, tzinfo=local_tz)
        to_end_exclusive = datetime.datetime.combine(
            to_date + datetime.timedelta(days=1),
            datetime.time.min,
            tzinfo=local_tz,
        )
        return self._fetch_rows_in_date_range(from_start, to_end_exclusive)

    @staticmethod
    def _fetch_latest_row() -> Optional[int]:
        """Read the latest UID from Postgres.

        Args:
            None.

        Returns:
            Latest logical_timeseries UID, or None if no rows.
        """
        query = """
            SELECT uid
            FROM logical_timeseries
            ORDER BY uid DESC
            LIMIT 1
        """
        pool = DeliveryDbReader._get_db_pool()
        conn = pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as curs:
                curs.execute(query)
                row = curs.fetchone()
                if row is None:
                    return None
                return row[0]
        finally:
            pool.putconn(conn)

    @classmethod
    def _get_db_pool(cls) -> SimpleConnectionPool:
        """Get or create the shared Postgres connection pool.

        Args:
            None.

        Returns:
            Shared process-local connection pool.

        Raises:
            Exception: If the DB is unavailable.
        """
        if cls._db_pool is None:
            pool = SimpleConnectionPool(1, 5, connect_timeout=5)
            conn = None
            try:
                conn = pool.getconn()
                conn.autocommit = True
                with conn.cursor() as curs:
                    curs.execute('SELECT 1')
            except Exception:
                pool.closeall()
                raise
            finally:
                if conn is not None:
                    pool.putconn(conn)
            cls._db_pool = pool
        if cls._db_pool is None:
            raise RuntimeError('Database pool initialisation failed.')
        return cls._db_pool

    @classmethod
    def close_db_pool(cls) -> None:
        """Close and clear the shared Postgres connection pool.

        Args:
            None.

        Returns:
            None.
        """
        if cls._db_pool is not None:
            cls._db_pool.closeall()
            cls._db_pool = None

    @staticmethod
    def _fetch_new_rows(last_uid: int) -> List[LogicalTimeseriesRow]:
        """Read rows newer than checkpoint.

        Args:
            last_uid: Last processed `uid`.

        Returns:
            Ordered list of new rows by `uid`.
        """
        query = """
            SELECT uid, physical_uid, logical_uid, ts, received_at, json_msg
            FROM logical_timeseries
            WHERE uid > %s
            ORDER BY uid ASC
        """
        pool = DeliveryDbReader._get_db_pool()
        conn = pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as curs:
                curs.execute(query, (last_uid,))
                return [
                    LogicalTimeseriesRow(
                        uid=row[0],
                        physical_uid=row[1],
                        logical_uid=row[2],
                        ts=row[3],
                        received_at=row[4],
                        json_msg=row[5],
                    )
                    for row in curs.fetchall()
                ]
        finally:
            pool.putconn(conn)

    @staticmethod
    def _fetch_rows_in_date_range(
        from_start: datetime.datetime,
        to_end_exclusive: datetime.datetime,
    ) -> List[LogicalTimeseriesRow]:
        """Read rows in a timestamp window.

        Args:
            from_start: Inclusive lower timestamp bound.
            to_end_exclusive: Exclusive upper timestamp bound.

        Returns:
            Ordered rows in window.
        """
        query = """
            SELECT uid, physical_uid, logical_uid, ts, received_at, json_msg
            FROM logical_timeseries
            WHERE ts >= %s
              AND ts < %s
            ORDER BY ts ASC, uid ASC
        """
        pool = DeliveryDbReader._get_db_pool()
        conn = pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as curs:
                curs.execute(query, (from_start, to_end_exclusive))
                return [
                    LogicalTimeseriesRow(
                        uid=row[0],
                        physical_uid=row[1],
                        logical_uid=row[2],
                        ts=row[3],
                        received_at=row[4],
                        json_msg=row[5],
                    )
                    for row in curs.fetchall()
                ]
        finally:
            pool.putconn(conn)

    @staticmethod
    @cache
    def fetch_logical_device_name(logical_uid: int) -> Optional[str]:
        """Read logical device name for a UID with process-local cache.

        Args:
            logical_uid: UID in logical_devices table.

        Returns:
            Logical device name, or None if no row exists.
        """
        query = "SELECT name FROM logical_devices WHERE uid = %s"
        pool = DeliveryDbReader._get_db_pool()
        conn = pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as curs:
                curs.execute(query, (logical_uid,))
                row = curs.fetchone()
                if row is None:
                    return None
                return row[0]
        finally:
            pool.putconn(conn)

    def _process_rows(self, rows: List[LogicalTimeseriesRow]) -> None:
        """Resolve logical names and delegate each row for delivery.

        Args:
            rows: Rows to process.

        Returns:
            None.
        """
        for row in rows:
            logical_name = self.fetch_logical_device_name(row.logical_uid)
            logger.info(f'Delivering row for {row.logical_uid} / {logical_name}: {json.dumps(row.json_msg)}')
            if logical_name is None:
                logger.info(
                    "[db-skip] uid=%s logical_uid=%s not found in logical_devices.",
                    row.uid,
                    row.logical_uid,
                )
                continue
            self.deliver_row(row, logical_name)

    def _monitor_logical_timeseries(self, stop_requested: Callable[[], bool]) -> None:
        """Continuously poll DB and deliver rows.

        Args:
            stop_requested: Callable returning True when loop should stop.

        Returns:
            None.
        """
        last_uid = self._fetch_latest_row()
        self._last_uid = 0 if last_uid is None else last_uid
        self._checkpoint_initialised = True

        logger.info(
            "Postgres monitor started for logical_timeseries where logical_uid is not null (poll=%.1fs).",
            self.poll_interval_seconds,
        )

        while not stop_requested():
            self.check_transport_health()

            if not self._checkpoint_initialised:
                raise RuntimeError("Database monitor not initialised.")

            rows = self._fetch_new_rows(self._last_uid)
            if rows:
                self._last_uid = rows[-1].uid

            self._process_rows(rows)
            self.check_transport_health()

            deadline = time.monotonic() + self.poll_interval_seconds
            while not stop_requested():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(0.2, remaining))

    def run(self, argv: Optional[List[str]] = None) -> None:
        """Run one-shot replay or live DB polling mode.

        Args:
            argv: Optional CLI argument list. Uses process args when None.

        Returns:
            None.
        """
        # Parse, validate, and apply args first.
        args = self.build_arg_parser().parse_args(argv)
        try:
            from_date, to_date = self.validate_date_args(args.from_date, args.to_date)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        self.apply_runtime_args(args)

        stop_flag = False
        previous_handlers: dict[int, Any] = {}

        def _stop_requested() -> bool:
            return stop_flag

        def _handle_signal(signum, frame):
            nonlocal stop_flag
            stop_flag = True

        self.connect_transport()
        try:
            if from_date is not None:
                logger.info(
                    "Processing logical_timeseries rows for date range %s to %s.",
                    from_date.isoformat(),
                    to_date.isoformat(),
                )
                total_rows = 0
                current_date = from_date
                while current_date <= to_date:
                    self.check_transport_health()
                    logger.info("Processing day %s.", current_date.isoformat())
                    rows = self.fetch_rows_in_date_range(current_date, current_date)
                    self._process_rows(rows)
                    total_rows += len(rows)
                    logger.info("Completed day %s. Rows read: %s", current_date.isoformat(), len(rows))
                    current_date += datetime.timedelta(days=1)

                logger.info("Completed one-shot date-range processing. Total rows read: %s", total_rows)
                return

            for sig in (signal.SIGINT, signal.SIGTERM):
                previous_handlers[sig] = signal.getsignal(sig)
                signal.signal(sig, _handle_signal)

            self._monitor_logical_timeseries(_stop_requested)
        finally:
            for sig, handler in previous_handlers.items():
                signal.signal(sig, handler)
            self.close_db_pool()
            self.close_transport()
            logger.info("Disconnected.")

    @abstractmethod
    def connect_transport(self) -> None:
        """Establish delivery transport connection.

        Args:
            None.

        Returns:
            None.
        """

    def parser_description(self) -> str:
        """Return parser description text.

        Args:
            None.

        Returns:
            Parser description text.
        """

    @abstractmethod
    def add_subclass_args(self, parser: argparse.ArgumentParser) -> None:
        """Add subclass-specific CLI arguments.

        Args:
            parser: Parser to extend.

        Returns:
            None.
        """

    @abstractmethod
    def apply_runtime_args(self, args: argparse.Namespace) -> None:
        """Apply parsed CLI args to runtime instance state.

        Args:
            args: Parsed CLI args.

        Returns:
            None.
        """

    @abstractmethod
    def close_transport(self) -> None:
        """Close delivery transport connection.

        Args:
            None.

        Returns:
            None.
        """

    @abstractmethod
    def check_transport_health(self) -> None:
        """Raise when transport is in failed state.

        Args:
            None.

        Returns:
            None.
        """

    @abstractmethod
    def deliver_row(self, row: LogicalTimeseriesRow, logical_device_name: str) -> None:
        """Transform and deliver one DB row to destination transport.

        Args:
            row: Source database row.
            logical_device_name: Resolved logical device name.

        Returns:
            None.
        """
