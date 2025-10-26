from __future__ import annotations

from pathlib import Path

from agentforge_cli import constants
from agentforge_cli.queue import TaskStore, run_task_loop


def test_spawn_agents_process_queue(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTFORGE_HOME", str(tmp_path))
    constants.refresh_paths()
    store = TaskStore(constants.TASK_DB)
    try:
        for idx in range(50):
            store.add_task(f"integration task {idx}")
    finally:
        store.close()

    run_task_loop(concurrency=20, autoscale=True)

    store = TaskStore(constants.TASK_DB)
    try:
        stats = store.stats()
    finally:
        store.close()

    assert stats["completed"] == 50
    assert stats["pending"] == 0
    assert stats["failed"] == 0
