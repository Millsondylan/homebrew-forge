from __future__ import annotations

import types

import pytest

from agentforge_cli import constants
from agentforge_cli.queue import TaskStore, run_task_loop


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTFORGE_HOME", str(tmp_path))
    constants.refresh_paths()
    yield


def test_shutdown_requeues_running_tasks(monkeypatch):
    store = TaskStore(constants.TASK_DB)
    try:
        for idx in range(3):
            store.add_task(f"shutdown task {idx}")
    finally:
        store.close()

    def interrupting_run(self):  # pragma: no cover - intentionally raises
        raise KeyboardInterrupt

    monkeypatch.setattr(
        "agentforge_cli.queue.AgentDispatcher.run",
        interrupting_run,
    )

    run_task_loop(concurrency=2, autoscale=False)

    store = TaskStore(constants.TASK_DB)
    try:
        stats = store.stats()
        assert stats["pending"] == 3
        assert stats["running"] == 0
    finally:
        store.close()
