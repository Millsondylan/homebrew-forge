from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from agentforge_cli.runtime.dispatcher import AgentDispatcher, AutoscaleState
from agentforge_cli.queue import TaskStore, Task


@pytest.fixture
def store(tmp_path: Path) -> TaskStore:
    path = tmp_path / "tasks.db"
    store = TaskStore(path)
    try:
        yield store
    finally:
        store.close()


def _add_tasks(store: TaskStore, count: int) -> None:
    for idx in range(count):
        store.add_task(f"task-{idx}")


def test_dispatcher_processes_tasks(store: TaskStore) -> None:
    _add_tasks(store, 5)
    completed: List[int] = []

    def process(worker_id: int, task_store: TaskStore, task: Task, model: str) -> None:
        completed.append(task.id)
        task_store.complete_task(task.id, f"done:{model}")

    dispatcher = AgentDispatcher(
        store=store,
        agent_model="claude",
        process=process,
        initial_concurrency=2,
    )
    dispatcher.run()
    assert len(completed) == 5
    stats = store.stats()
    assert stats["pending"] == 0
    assert stats["completed"] == 5


def test_dispatcher_autoscale_adjusts_target(store: TaskStore) -> None:
    _add_tasks(store, 15)
    completed: List[int] = []

    def process(worker_id: int, task_store: TaskStore, task: Task, model: str) -> None:
        completed.append(task.id)
        task_store.complete_task(task.id, "done")

    autoscale_state = AutoscaleState(
        enabled=True,
        max_concurrency=20,
        scale_up_pending_per_worker=1,
        scale_down_idle_cycles=1,
    )

    dispatcher = AgentDispatcher(
        store=store,
        agent_model="claude",
        process=process,
        initial_concurrency=2,
        autoscale=autoscale_state,
    )
    dispatcher.run()
    assert len(completed) == 15
    assert dispatcher.target_concurrency >= 2

    stats = store.stats()
    assert stats["pending"] == 0
