from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentforge_cli import constants
from agentforge_cli.queue import TaskStore, run_task_loop
from agentforge_cli.verification import export_verification_report


@pytest.fixture(autouse=True)
def set_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENTFORGE_HOME", str(tmp_path))
    constants.refresh_paths()
    yield


def test_verification_log_records_checks(tmp_path: Path):
    store = TaskStore(constants.TASK_DB)
    try:
        store.add_task("Write integration tests")
    finally:
        store.close()

    run_task_loop(concurrency=1, autoscale=False)

    verification_log = constants.LOG_DIR / "verification.log"
    assert verification_log.exists()
    entries = [json.loads(line) for line in verification_log.read_text().splitlines() if line]
    checks = {entry["check"] for entry in entries}
    assert {"logical", "empirical"}.issubset(checks)
    assert all(entry["passed"] for entry in entries)

    report_path = export_verification_report()
    assert report_path.exists()
    exported = json.loads(report_path.read_text())
    assert len(exported) >= 2
