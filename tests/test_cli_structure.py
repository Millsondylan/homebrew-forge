from click.testing import CliRunner

from agentforge_cli.cli import cli


def test_root_commands_present() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    for command in ("init", "auth", "model", "agent", "queue", "schedule", "monitor", "status", "/login"):
        assert command in cli.commands, f"{command} command missing"


def test_auth_group_contains_providers() -> None:
    auth_group = cli.commands["auth"]
    assert {"anthropic", "openai", "gemini"}.issubset(auth_group.commands.keys())


def test_model_group_subcommands() -> None:
    model_group = cli.commands["model"]
    assert {"list", "set", "select"}.issubset(model_group.commands.keys())


def test_queue_group_subcommands() -> None:
    queue_group = cli.commands["queue"]
    assert {"add", "list", "run"}.issubset(queue_group.commands.keys())


def test_schedule_group_subcommands() -> None:
    schedule_group = cli.commands["schedule"]
    assert {"add", "run"}.issubset(schedule_group.commands.keys())
