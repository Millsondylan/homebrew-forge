from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from agentforge_cli.cli import cli


@pytest.fixture
def runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    monkeypatch.setenv("AGENTFORGE_HOME", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    return runner


def test_new_command_clears_cnovo(runner: CliRunner, tmp_path: Path) -> None:
    cnovo_dir = tmp_path / "cnovo"
    cnovo_dir.mkdir(exist_ok=True)
    (cnovo_dir / "temp.txt").write_text("data", encoding="utf-8")

    result = runner.invoke(cli, ["/new"])
    assert result.exit_code == 0
    assert list(cnovo_dir.iterdir()) == []
