from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from agentforge_cli.memory import MemoryStore
from agentforge_cli.cli import cli


def test_memory_store_add_and_search(tmp_path: Path) -> None:
    store_path = tmp_path / "memory.db"
    with MemoryStore(store_path) as store:
        store.add_memory("agent-001", "Implemented OAuth flow", {"task_id": 1})
        store.add_memory("agent-002", "Refined scheduler cron support", {"task_id": 2})
        results = store.search("scheduler")
    assert results and results[0].metadata["task_id"] == 2


def test_memory_cli_search(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("AGENTFORGE_HOME", str(home))
    runner = CliRunner()
    runner.invoke(cli, ["init"])
    with MemoryStore(home / "db" / "memory.db") as store:
        store.add_memory("agent-001", "Queue retry backoff implemented", {"task_id": 10})
    result = runner.invoke(cli, ["memory", "search", "backoff"])
    assert result.exit_code == 0
    assert "backoff" in result.output.lower()
