from __future__ import annotations

from pathlib import Path

from agentforge_cli import constants
from agentforge_cli.loadtest import run_load_test


def test_run_load_test(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTFORGE_HOME", str(tmp_path))
    constants.refresh_paths()
    report = tmp_path / "reports" / "summary.json"
    result = run_load_test(agents=5, tasks=10, report_path=report, reset=True)
    assert report.exists()
    data = report.read_text()
    assert "duration_seconds" in data
    assert result["queue_stats"]["completed"] == 10
