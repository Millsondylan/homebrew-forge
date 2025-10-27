"""
Command palette for AgentForge CLI.

Interactive command browser with search and selection.
"""

from __future__ import annotations

import click
from typing import Any, Dict, List, Optional, Tuple


def build_command_catalog(cli_group: click.Group) -> List[Dict[str, Any]]:
    """
    Build catalog of all CLI commands.

    Args:
        cli_group: Click CLI group

    Returns:
        List of command metadata dictionaries
    """
    commands = []

    def extract_commands(group: click.Group, prefix: str = ""):
        """Recursively extract commands from groups."""
        for name, cmd in group.commands.items():
            full_name = f"{prefix}{name}" if prefix else name

            if isinstance(cmd, click.Group):
                # Recurse into subgroups
                extract_commands(cmd, prefix=f"{full_name} ")
            else:
                # Regular command
                commands.append({
                    "name": full_name,
                    "help": cmd.help or "No description available",
                    "short_help": cmd.short_help or cmd.help or "",
                    "params": [p.name for p in cmd.params if not p.hidden],
                })

    extract_commands(cli_group)

    return sorted(commands, key=lambda x: x["name"])


def group_commands(commands: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group commands by category.

    Args:
        commands: List of command dictionaries

    Returns:
        Dictionary mapping category to commands
    """
    groups = {
        "Core": [],
        "Auth": [],
        "Model": [],
        "Queue": [],
        "Agent": [],
        "Schedule": [],
        "Memory": [],
        "Monitor": [],
        "Verify": [],
        "Other": [],
    }

    for cmd in commands:
        name = cmd["name"]

        # Categorize
        if name.startswith("auth"):
            groups["Auth"].append(cmd)
        elif name.startswith("model") or name in ["/model", "/agentmodel"]:
            groups["Model"].append(cmd)
        elif name.startswith("queue"):
            groups["Queue"].append(cmd)
        elif name.startswith("agent"):
            groups["Agent"].append(cmd)
        elif name.startswith("schedule"):
            groups["Schedule"].append(cmd)
        elif name.startswith("memory"):
            groups["Memory"].append(cmd)
        elif name.startswith("monitor") or name == "status" or name == "dashboard":
            groups["Monitor"].append(cmd)
        elif name.startswith("verify"):
            groups["Verify"].append(cmd)
        elif name in ["init", "plan", "resume", "/plan", "/resume", "/login", "/new"]:
            groups["Core"].append(cmd)
        else:
            groups["Other"].append(cmd)

    # Remove empty groups
    return {k: v for k, v in groups.items() if v}


def filter_commands(query: str, commands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter commands by fuzzy search query.

    Args:
        query: Search query
        commands: List of command dictionaries

    Returns:
        Filtered list of commands
    """
    if not query:
        return commands

    query_lower = query.lower()
    filtered = []

    for cmd in commands:
        # Check name match
        if query_lower in cmd["name"].lower():
            filtered.append(cmd)
            continue

        # Check description match
        if query_lower in cmd["help"].lower():
            filtered.append(cmd)
            continue

    return filtered


def highlight_matches(query: str, text: str) -> str:
    """
    Highlight query matches in text.

    Args:
        query: Search query
        text: Text to highlight

    Returns:
        Text with highlighted matches
    """
    if not query:
        return text

    # Simple case-insensitive highlight
    # In a real terminal UI, this would use ANSI codes
    query_lower = query.lower()
    text_lower = text.lower()

    if query_lower in text_lower:
        idx = text_lower.index(query_lower)
        return (
            text[:idx] +
            f"[{text[idx:idx + len(query)]}]" +
            text[idx + len(query):]
        )

    return text


def format_command_display(cmd: Dict[str, Any], width: int = 80) -> str:
    """
    Format command for display.

    Args:
        cmd: Command dictionary
        width: Display width

    Returns:
        Formatted command string
    """
    name = cmd["name"]
    help_text = cmd["short_help"] or cmd["help"]

    # Truncate help if too long
    max_help_len = width - len(name) - 5
    if len(help_text) > max_help_len:
        help_text = help_text[:max_help_len - 3] + "..."

    return f"  {name:<30} {help_text}"


def display_palette(
    commands: List[Dict[str, Any]],
    grouped: bool = True,
    search_query: str = ""
) -> None:
    """
    Display command palette.

    Args:
        commands: List of command dictionaries
        grouped: Whether to group by category
        search_query: Current search query
    """
    if grouped:
        groups = group_commands(commands)

        for category, cmds in groups.items():
            click.echo(f"\n{category}:")
            for cmd in cmds:
                display_text = format_command_display(cmd)
                if search_query:
                    display_text = highlight_matches(search_query, display_text)
                click.echo(display_text)
    else:
        for idx, cmd in enumerate(commands, 1):
            display_text = f"{idx}. {format_command_display(cmd)}"
            if search_query:
                display_text = highlight_matches(search_query, display_text)
            click.echo(display_text)


def select_command_simple(commands: List[Dict[str, Any]]) -> Optional[str]:
    """
    Simple command selection using numbered list.

    Args:
        commands: List of command dictionaries

    Returns:
        Selected command name or None
    """
    if not commands:
        return None

    # Display commands with numbers
    display_palette(commands, grouped=False)

    click.echo("")
    choice = click.prompt(
        "Select command number (or 'q' to cancel)",
        type=str,
        default="q"
    )

    if choice.lower() == "q":
        return None

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(commands):
            return commands[idx]["name"]
    except ValueError:
        pass

    return None


def search_and_select(cli_group: click.Group) -> Optional[Tuple[str, List[str]]]:
    """
    Interactive search and command selection.

    Args:
        cli_group: Click CLI group

    Returns:
        Tuple of (command_name, args) or None if cancelled
    """
    commands = build_command_catalog(cli_group)

    click.echo("=== AgentForge Command Palette ===")
    click.echo("")

    # Interactive search loop
    while True:
        search_query = click.prompt(
            "Search commands (or 'q' to cancel, Enter to see all)",
            type=str,
            default=""
        )

        if search_query.lower() == "q":
            return None

        # Filter commands
        filtered = filter_commands(search_query, commands)

        if not filtered:
            click.echo("No commands found.")
            continue

        click.echo(f"\nFound {len(filtered)} command(s):")
        click.echo("")

        # Select command
        selected = select_command_simple(filtered)

        if selected:
            # Prompt for arguments if command has params
            cmd_info = next(c for c in filtered if c["name"] == selected)

            if cmd_info["params"]:
                click.echo(f"\nCommand '{selected}' accepts parameters: {', '.join(cmd_info['params'])}")
                args_input = click.prompt(
                    "Enter arguments (space-separated, or Enter for none)",
                    type=str,
                    default=""
                )
                args = args_input.split() if args_input else []
            else:
                args = []

            return (selected, args)


def execute_command_from_palette(cli_group: click.Group, ctx: click.Context) -> None:
    """
    Execute command selected from palette.

    Args:
        cli_group: Click CLI group
        ctx: Click context
    """
    result = search_and_select(cli_group)

    if result:
        command_name, args = result
        click.echo(f"\nExecuting: forge {command_name} {' '.join(args)}")
        click.echo("")

        # Parse command path (handle subcommands like "model set")
        parts = command_name.split()

        try:
            # Navigate to command
            cmd = cli_group
            for part in parts:
                if isinstance(cmd, click.Group):
                    cmd = cmd.commands.get(part)
                    if cmd is None:
                        click.echo(f"Command '{part}' not found.")
                        return
                else:
                    click.echo(f"'{part}' is not a group.")
                    return

            # Invoke command
            if isinstance(cmd, click.Command):
                ctx.invoke(cmd, *args)
            else:
                click.echo(f"'{command_name}' is not a command.")
        except Exception as e:
            click.echo(f"Error executing command: {e}")
    else:
        click.echo("Cancelled.")
