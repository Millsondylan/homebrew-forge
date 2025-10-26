from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from agentforge_cli.scheduler import ScheduleSpec, parse_schedule_time
from agentforge_cli.queue import TaskStore


@pytest.fixture
def store(tmp_path: Path) -> TaskStore:
    path = tmp_path / "scheduler.db"
    store = TaskStore(path)
    try:
        yield store
    finally:
        store.close()


def test_parse_relative_schedule() -> None:
    spec = parse_schedule_time("in:10s")
    assert isinstance(spec, ScheduleSpec)
    assert spec.cron_expression is None


def test_parse_cron_schedule() -> None:
    spec = parse_schedule_time(None, cron="*/5 * * * *")
    assert spec.cron_expression == "*/5 * * * *"


def test_cron_reschedules_until_max_runs(store: TaskStore, monkeypatch: pytest.MonkeyPatch) -> None:
    description = "run backup"
    initial_time = datetime.utcnow() - timedelta(seconds=1)
    schedule_id = store.add_scheduled_task(
        description,
        initial_time,
        cron_expression="*/1 * * * *",
        max_runs=2,
    )

    released = store.release_due_scheduled()
    assert released == 1
    row = store.conn.execute(
        "SELECT status, run_count FROM scheduled_tasks WHERE id = ?",
        (schedule_id,),
    ).fetchone()
    assert row["run_count"] == 1
    assert row["status"] == "pending"

    store.conn.execute(
        "UPDATE scheduled_tasks SET scheduled_for = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), schedule_id),
    )
    store.conn.commit()

    released = store.release_due_scheduled()
    assert released == 1
    row = store.conn.execute(
        "SELECT status, run_count FROM scheduled_tasks WHERE id = ?",
        (schedule_id,),
    ).fetchone()
    assert row["run_count"] == 2
    assert row["status"] == "completed"
