from __future__ import annotations

from click.testing import CliRunner

from agentforge_cli import constants
from agentforge_cli.cli import cli
from agentforge_cli.queue import TaskStore


def test_monitor_outputs_queue_stats(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTFORGE_HOME", str(tmp_path))
    constants.refresh_paths()
    runner = CliRunner()
    runner.invoke(cli, ["init"])
    store = TaskStore(constants.TASK_DB)
    try:
        store.add_task("document logging")
    finally:
        store.close()

    result = runner.invoke(cli, ["monitor", "--no-follow"])
    assert result.exit_code == 0
    assert "Queue status:" in result.output
    assert "pending" in result.output.lower()
