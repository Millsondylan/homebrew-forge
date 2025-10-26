"""
Scheduler helpers for AgentForge CLI.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Optional

import click

from . import constants
from .queue import TaskStore
from .constants import SCHEDULE_POLL_INTERVAL
from .logger import write_system_log


def parse_schedule_time(value: str) -> datetime:
    """Parse ISO timestamps or relative durations prefixed with 'in:'."""
    value = value.strip()
    if value.startswith("in:"):
        offset = value[3:]
        quantity = int(offset[:-1])
        unit = offset[-1]
        delta: Optional[timedelta] = None
        if unit == "s":
            delta = timedelta(seconds=quantity)
        elif unit == "m":
            delta = timedelta(minutes=quantity)
        elif unit == "h":
            delta = timedelta(hours=quantity)
        else:
            raise click.BadParameter("Relative schedules must end with s/m/h, e.g. in:30m")
        return datetime.utcnow() + delta
    return datetime.fromisoformat(value)


def add_scheduled_task(description: str, when: datetime) -> int:
    constants.refresh_paths()
    store = TaskStore(constants.TASK_DB)
    try:
        return store.add_scheduled_task(description, when)
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
