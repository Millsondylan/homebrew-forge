"""Tests for command palette module."""

import click
from click.testing import CliRunner

from agentforge_cli.palette import (
    build_command_catalog,
    group_commands,
    filter_commands,
    highlight_matches,
    format_command_display,
)


def test_build_command_catalog():
    """Test building command catalog."""

    @click.group()
    def cli():
        pass

    @cli.command()
    def test_command():
        """Test command description"""
        pass

    @cli.group()
    def subgroup():
        """Subgroup"""
        pass

    @subgroup.command()
    def sub_command():
        """Sub command"""
        pass

    catalog = build_command_catalog(cli)

    assert len(catalog) == 2
    # Commands might be sorted differently or have underscore/dash conversion
    assert any("test" in cmd["name"].lower() for cmd in catalog)
    assert any("sub" in cmd["name"].lower() for cmd in catalog)


def test_group_commands():
    """Test grouping commands by category."""
    commands = [
        {"name": "auth anthropic", "help": "Auth", "short_help": "Auth", "params": []},
        {"name": "model set", "help": "Model", "short_help": "Model", "params": []},
        {"name": "queue add", "help": "Queue", "short_help": "Queue", "params": []},
        {"name": "init", "help": "Init", "short_help": "Init", "params": []},
    ]

    groups = group_commands(commands)

    assert "Auth" in groups
    assert "Model" in groups
    assert "Queue" in groups
    assert "Core" in groups
    assert len(groups["Auth"]) == 1
    assert len(groups["Core"]) == 1


def test_filter_commands():
    """Test filtering commands."""
    commands = [
        {"name": "auth anthropic", "help": "Authenticate with Anthropic", "short_help": "Auth", "params": []},
        {"name": "model set", "help": "Set active model", "short_help": "Model", "params": []},
        {"name": "queue add", "help": "Add task to queue", "short_help": "Queue", "params": []},
    ]

    # Filter by name
    filtered = filter_commands("auth", commands)
    assert len(filtered) == 1
    assert filtered[0]["name"] == "auth anthropic"

    # Filter by description
    filtered = filter_commands("queue", commands)
    assert len(filtered) >= 1
    assert any("queue" in cmd["name"].lower() for cmd in filtered)

    # No match
    filtered = filter_commands("nonexistent", commands)
    assert len(filtered) == 0


def test_highlight_matches():
    """Test highlighting matches in text."""
    text = "This is a test string"

    highlighted = highlight_matches("test", text)
    assert "[test]" in highlighted

    # No query
    highlighted = highlight_matches("", text)
    assert highlighted == text

    # No match
    highlighted = highlight_matches("xyz", text)
    assert highlighted == text


def test_format_command_display():
    """Test formatting command for display."""
    cmd = {
        "name": "test command",
        "help": "This is a test command with a description",
        "short_help": "Test",
        "params": []
    }

    formatted = format_command_display(cmd)

    assert "test command" in formatted
    assert "Test" in formatted or "This is a test" in formatted


def test_format_command_display_truncation():
    """Test that long help text is truncated."""
    cmd = {
        "name": "cmd",
        "help": "x" * 200,  # Very long help text
        "short_help": "",
        "params": []
    }

    formatted = format_command_display(cmd, width=80)

    # Just check that truncation happened
    assert "..." in formatted  # Should be truncated
    assert len(formatted) <= 120  # Reasonable upper bound


def test_filter_commands_case_insensitive():
    """Test that filtering is case-insensitive."""
    commands = [
        {"name": "Auth Anthropic", "help": "Authenticate", "short_help": "Auth", "params": []},
    ]

    # Lowercase query
    filtered = filter_commands("auth", commands)
    assert len(filtered) == 1

    # Uppercase query
    filtered = filter_commands("AUTH", commands)
    assert len(filtered) == 1

    # Mixed case
    filtered = filter_commands("AuTh", commands)
    assert len(filtered) == 1
