from pathlib import Path

import pytest
from click.testing import CliRunner

from agentforge_cli.cli import cli


@pytest.mark.usefixtures("_reset_env_home")
def test_init_creates_directories(tmp_path, monkeypatch) -> None:
    home = tmp_path / "af_home"
    monkeypatch.setenv("AGENTFORGE_HOME", str(home))
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0, result.output

    expected_dirs = [
        home,
        home / "agents",
        home / "logs",
        home / "db",
        home / "schedules",
    ]
    for directory in expected_dirs:
        assert directory.is_dir(), f"Missing directory {directory}"

    env_file = home / ".env"
    assert env_file.is_file()
    env_content = env_file.read_text(encoding="utf-8")
    assert "AgentForge environment configuration" in env_content
    assert "OLLAMA_BASE_URL" in env_content

    config_file = home / "config.yaml"
    assert config_file.is_file()

    task_db = home / "db" / "tasks.db"
    assert task_db.is_file()


@pytest.fixture
def _reset_env_home(monkeypatch):
    """
    Ensure AGENTFORGE_HOME is unset after each test to avoid polluting the
    developer environment.
    """

    monkeypatch.delenv("AGENTFORGE_HOME", raising=False)
    yield
    monkeypatch.delenv("AGENTFORGE_HOME", raising=False)
