from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from agentforge_cli.cli import cli
from agentforge_cli.config import get_paths, load_config


@pytest.fixture
def runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    home = tmp_path / "af_home"
    monkeypatch.setenv("AGENTFORGE_HOME", str(home))
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    return runner


def test_model_set_updates_provider_mapping(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["model", "set", "anthropic:claude-3-5-haiku-20241022"])
    assert result.exit_code == 0, result.output
    config = load_config()
    assert config["models"]["primary"]["provider"] == "anthropic"
    assert config["models"]["primary"]["name"] == "claude-3-5-haiku-20241022"
    events = get_paths()["data_dir"] / "model_events.log"
    assert events.exists()
    log = events.read_text(encoding="utf-8").strip().splitlines()[-1]
    assert "anthropic" in log and "claude-3-5-haiku-20241022" in log


def test_agent_model_set_accepts_provider_prefix(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["agent", "model", "set", "anthropic:claude-3-opus-20240229"])
    assert result.exit_code == 0, result.output
    config = load_config()
    assert config["models"]["agent"]["name"] == "claude-3-opus-20240229"


def test_model_set_rejects_unknown_provider(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["model", "set", "unknown:demo"], catch_exceptions=False)
    assert result.exit_code != 0
    assert "Unknown model" in result.output or "provider" in result.output
