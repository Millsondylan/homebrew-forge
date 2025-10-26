from __future__ import annotations

from click.testing import CliRunner

from agentforge_cli import constants
from agentforge_cli.cli import cli
from agentforge_cli.queue import TaskStore


def test_verify_export_cli(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTFORGE_HOME", str(tmp_path))
    constants.refresh_paths()
    store = TaskStore(constants.TASK_DB)
    store.add_task("verification task")
    store.close()

    runner = CliRunner()
    runner.invoke(cli, ["agent", "spawn", "1"], catch_exceptions=False)
    result = runner.invoke(cli, ["verify", "export", "--output", str(tmp_path / "report.json")])
    assert result.exit_code == 0
    assert (tmp_path / "report.json").exists()
