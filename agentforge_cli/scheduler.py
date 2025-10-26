"""
Scheduler helpers for AgentForge CLI.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import click

from . import constants
from .queue import TaskStore
from .constants import SCHEDULE_POLL_INTERVAL
from .logger import write_system_log
from croniter import croniter


@dataclass
class ScheduleSpec:
    run_at: datetime
    cron_expression: Optional[str] = None
    timezone: str = "UTC"
    max_runs: Optional[int] = None


def _normalize_to_utc(dt: datetime, tz: Optional[str]) -> tuple[datetime, str]:
    if dt.tzinfo is not None:
        converted = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return converted, "UTC"
    tz_name = tz or "UTC"
    try:
        tzinfo = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise click.BadParameter(f"Unknown timezone '{tz_name}'") from exc
    localized = dt.replace(tzinfo=tzinfo)
    converted = localized.astimezone(timezone.utc).replace(tzinfo=None)
    return converted, tz_name


def parse_schedule_time(value: Optional[str], *, cron: Optional[str] = None, tz: Optional[str] = None, max_runs: Optional[int] = None) -> ScheduleSpec:
    """Parse schedule input into a structured specification."""
    expression = cron
    if value:
        stripped = value.strip()
        if stripped.lower().startswith("cron:"):
            expression = stripped.split(":", 1)[1].strip()
    tz_name = tz or "UTC"
    try:
        tzinfo = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise click.BadParameter(f"Unknown timezone '{tz_name}'") from exc

    if expression:
        base = datetime.now(tzinfo)
        try:
            iterator = croniter(expression, base)
        except (ValueError, KeyError) as exc:
            raise click.BadParameter(f"Invalid cron expression: {exc}") from exc
        next_run_local = iterator.get_next(datetime)
        run_at, tz_record = _normalize_to_utc(next_run_local, tz_name)
        if max_runs is not None and max_runs < 1:
            raise click.BadParameter("max-runs must be at least 1 for cron schedules")
        return ScheduleSpec(run_at=run_at, cron_expression=expression, timezone=tz_record, max_runs=max_runs)

    if not value:
        raise click.BadParameter("A schedule time or cron expression is required")

    stripped = value.strip()
    if stripped.startswith("in:"):
        offset = stripped[3:]
        quantity = int(offset[:-1])
        unit = offset[-1]
        if unit == "s":
            delta = timedelta(seconds=quantity)
        elif unit == "m":
            delta = timedelta(minutes=quantity)
        elif unit == "h":
            delta = timedelta(hours=quantity)
        else:
            raise click.BadParameter("Relative schedules must end with s/m/h, e.g. in:30m")
        return ScheduleSpec(run_at=datetime.utcnow() + delta, cron_expression=None, timezone="UTC")

    parsed = datetime.fromisoformat(stripped)
    run_at, tz_record = _normalize_to_utc(parsed, tz_name)
    return ScheduleSpec(run_at=run_at, cron_expression=None, timezone=tz_record)


def add_scheduled_task(description: str, spec: ScheduleSpec) -> int:
    constants.refresh_paths()
    store = TaskStore(constants.TASK_DB)
    try:
        return store.add_scheduled_task(
            description,
            spec.run_at,
            cron_expression=spec.cron_expression,
            timezone=spec.timezone,
            max_runs=spec.max_runs,
        )
    finally:
        store.close()


def release_due_tasks(limit: Optional[int] = None) -> int:
    constants.refresh_paths()
    store = TaskStore(constants.TASK_DB)
    try:
        return store.release_due_scheduled(limit=limit)
    finally:
        store.close()


def run_schedule_loop(poll_seconds: Optional[int] = None, once: bool = False) -> None:
    """Move scheduled tasks into the live queue."""
    interval = SCHEDULE_POLL_INTERVAL if poll_seconds is None else timedelta(seconds=poll_seconds)
    write_system_log("Scheduler started")
    while True:
        released = release_due_tasks()
        if released:
            write_system_log(f"Scheduler released {released} task(s)")
        if once:
            break
        click.echo(f"Scheduler sleeping for {interval.total_seconds()}s… (Ctrl+C to stop)")
        try:
            time.sleep(interval.total_seconds())
        except KeyboardInterrupt:
            write_system_log("Scheduler stopped by user")
            break
