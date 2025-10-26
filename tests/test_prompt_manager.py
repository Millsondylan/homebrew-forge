from __future__ import annotations

from click.testing import CliRunner

from agentforge_cli.prompts import SystemPromptManager
from agentforge_cli.cli import cli


def test_prompt_render_contains_rules() -> None:
    manager = SystemPromptManager()
    rendered = manager.render("Implement autoscaling", context=["Previous autoscale config"], verification_steps=["Verify metrics"])
    assert "autoscaling" in rendered.system_prompt.lower()
    assert any("truth" in rule.lower() for rule in rendered.rules)
    assert "verify metrics" in rendered.system_prompt.lower()


def test_prompt_preview_cli(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("AGENTFORGE_HOME", str(home))
    runner = CliRunner()
    runner.invoke(cli, ["init"])
    result = runner.invoke(cli, ["prompt", "preview", "Write docs", "--context", "memory line"])
    assert result.exit_code == 0
    assert "write docs" in result.output.lower()
    assert "memory line" in result.output
