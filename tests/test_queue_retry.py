from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import pytest

from agentforge_cli.queue import TaskStore


@pytest.fixture
def store(tmp_path: Path) -> TaskStore:
    path = tmp_path / "queue.db"
    store = TaskStore(path)
    try:
        yield store
    finally:
        store.close()


def test_idempotent_enqueue(store: TaskStore) -> None:
    first = store.add_task("build docs", idempotency_key="task-docs")
    second = store.add_task("build docs", idempotency_key="task-docs")
    assert first == second


def test_retry_backoff_and_delay(store: TaskStore) -> None:
    task_id = store.add_task("flaky", max_attempts=2)
    task = store.claim_task()
    assert task is not None
    assert task.id == task_id
    store.fail_task(task, "boom")

    stats = store.stats()
    assert stats["pending"] == 0
    assert stats["delayed"] == 1

    time.sleep(2.2)
    retry_task = store.claim_task()
    assert retry_task is not None
    store.complete_task(retry_task.id, "ok")


def test_fail_after_max_attempts(store: TaskStore) -> None:
    task_id = store.add_task("single-shot", max_attempts=1)
    task = store.claim_task()
    store.fail_task(task, "still broken")
    stats = store.stats()
    assert stats["failed"] == 1
    assert stats["pending"] == 0
