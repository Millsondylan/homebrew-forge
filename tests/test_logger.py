from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentforge_cli import constants
from agentforge_cli.logger import agent_log_path, write_agent_log, write_system_log


@pytest.fixture(autouse=True)
def set_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENTFORGE_HOME", str(tmp_path))
    constants.refresh_paths()
    yield


def test_agent_logs_are_json(tmp_path: Path):
    write_agent_log(1, "Executed task", extra={"task_id": 123})
    path = agent_log_path(1)
    data = [json.loads(line) for line in path.read_text().splitlines() if line]
    assert data[0]["agent_id"] == "agent-001"
    assert data[0]["task_id"] == 123


def test_system_log_rotation(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("agentforge_cli.logger.MAX_LOG_BYTES", 200)
    for idx in range(50):
        write_system_log(f"entry {idx}")
    log_path = constants.SYSTEM_LOG_FILE
    assert log_path.exists()
    rotated = Path(f"{log_path}.1")
    assert rotated.exists()
    with log_path.open("r", encoding="utf-8") as fh:
        json.loads(fh.readline())
