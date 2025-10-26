from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from agentforge_cli.cli import cli
from agentforge_cli.reports import generate_final_report


def test_generate_final_report(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".agentforge").mkdir()
    todos = {
        "todos": [
            {"id": "01", "label": "core", "description": "Example", "status": "completed"}
        ]
    }
    (tmp_path / ".agentforge" / "todos.json").write_text(json.dumps(todos), encoding="utf-8")
    report_path = generate_final_report(tmp_path / "reports" / "final.json")
    data = json.loads(report_path.read_text())
    assert data["todos"][0]["id"] == "01"


def test_verify_final_report_cli(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".agentforge").mkdir()
    todos = {
        "todos": [
            {"id": "01", "label": "core", "description": "Example", "status": "completed"}
        ]
    }
    (tmp_path / ".agentforge" / "todos.json").write_text(json.dumps(todos), encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(cli, ["verify", "final-report", "--output", str(tmp_path / "reports" / "final.json")])
    assert result.exit_code == 0
    assert (tmp_path / "reports" / "final.json").exists()
