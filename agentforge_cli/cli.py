"""
Command-line interface for AgentForge.
"""

from __future__ import annotations

import click
import webbrowser
from datetime import datetime
from typing import Optional
import shutil
import subprocess

from .config import (
    ensure_directories,
    load_config,
    record_login,
    set_active_model,
    set_agent_model,
    store_key,
    get_paths,
    export_state,
)
from .constants import ANTHROPIC_LOGIN_URL, DEFAULT_MODELS
from .logger import init_logging, write_system_log
from .queue import TaskStore, run_task_loop
from .scheduler import add_scheduled_task, parse_schedule_time, run_schedule_loop
from . import get_version


def _prompt_model_choice(models: list[str], label: str) -> str:
    click.echo(f"Available {label}:")
    for idx, model in enumerate(models, start=1):
        click.echo(f"  {idx}. {model}")
    choice = click.prompt(f"Select {label} by number", type=click.IntRange(1, len(models)))
    return models[choice - 1]


@click.group()
@click.version_option(get_version(), prog_name="AgentForge")
def cli() -> None:
    """AgentForge CLI."""


@cli.command()
def init() -> None:
    """Initialise configuration, database, and log folders."""
    ensure_directories()
    config = load_config()
    store = TaskStore(get_paths()["task_db"])
    store.close()
    click.echo(f"Configuration ready at {get_paths()['config_root']}")


@cli.group()
def auth() -> None:
    """Authentication helpers."""


@auth.command()
def anthropic() -> None:
    """Launch browser login for Anthropic."""
    anthropic_cli = shutil.which("anthropic")
    if anthropic_cli:
        click.echo("Starting Anthropic CLI login flow…")
        try:
            subprocess.run([anthropic_cli, "login"], check=True)
            record_login(datetime.utcnow())
            write_system_log("Anthropic CLI login completed")
            click.echo("Anthropic login completed. Credentials cached by Anthropic tooling.")
            return
        except subprocess.CalledProcessError as exc:  # pragma: no cover - external dependency
            write_system_log(f"Anthropic CLI login failed: {exc}")
            click.echo("Anthropic CLI login failed, falling back to direct browser flow.")
    login_url = load_config().get("anthropic_login_url", ANTHROPIC_LOGIN_URL)
    click.echo("Opening browser for Anthropic login…")
    webbrowser.open(login_url, new=1)
    record_login(datetime.utcnow())
    write_system_log("Anthropic login triggered via direct browser flow")
    click.echo("Complete the Anthropic login in your browser to finish authentication.")


@auth.command()
@click.argument("api_key")
def openai(api_key: str) -> None:
    """Store OpenAI API key."""
    store_key("openai", api_key)
    click.echo("OpenAI key saved.")


@auth.command()
@click.argument("api_key")
def gemini(api_key: str) -> None:
    """Store Gemini API key."""
    store_key("gemini", api_key)
    click.echo("Gemini key saved.")


@cli.command(name="/login")
def slash_login() -> None:
    """Slash command wrapper for anthropic auth."""
    cli_ctx = click.get_current_context()
    cli_ctx.invoke(anthropic)


@cli.command(name="/model")
def slash_model() -> None:
    """Slash command to pick the primary model."""
    config = load_config()
    models = config.get("available_models", DEFAULT_MODELS)
    chosen = _prompt_model_choice(models, "models")
    set_active_model(chosen)
    click.echo(f"Primary model set to {chosen}")


@cli.command(name="/agentmodel")
def slash_agent_model() -> None:
    """Slash command to update the workforce agent model."""
    config = load_config()
    models = config.get("available_models", DEFAULT_MODELS)
    chosen = _prompt_model_choice(models, "agent models")
    set_agent_model(chosen)
    click.echo(f"Agent workforce model set to {chosen}")


@cli.group()
def model() -> None:
    """Model management."""


@model.command()
def list() -> None:  # type: ignore[override]
    """List available models."""
    config = load_config()
    active = config["active_model"]
    agent_model = config["agent_model"]
    for model_name in config["available_models"]:
        marker = []
        if model_name == active:
            marker.append("active")
        if model_name == agent_model:
            marker.append("agent")
        suffix = f" ({', '.join(marker)})" if marker else ""
        click.echo(f"- {model_name}{suffix}")


@model.command()
@click.argument("model_name")
def set(model_name: str) -> None:
    """Set the active model."""
    set_active_model(model_name)
    click.echo(f"Primary model set to {model_name}")


@model.command()
def select() -> None:
    """Interactive selection of the active model."""
    cli_ctx = click.get_current_context()
    cli_ctx.invoke(slash_model)


@cli.group()
def queue() -> None:
    """Task queue operations."""


@queue.command()
@click.argument("task_description")
@click.option("--agent-model", "agent_model", default=None, help="Override agent model for this task.")
def add(task_description: str, agent_model: Optional[str]) -> None:
    """Add a task to the queue."""
    store = TaskStore(get_paths()["task_db"])
    try:
        task_id = store.add_task(task_description, agent_model)
        click.echo(f"Task {task_id} added.")
    finally:
        store.close()


@queue.command()
@click.option("--limit", default=None, type=int, help="Limit number of tasks listed.")
def list(limit: Optional[int]) -> None:  # type: ignore[override]
    """List tasks in the queue."""
    store = TaskStore(get_paths()["task_db"])
    try:
        tasks = store.list_tasks(limit=limit)
    finally:
        store.close()
    if not tasks:
        click.echo("No tasks in queue.")
        return
    for task in tasks:
        click.echo(
            f"#{task.id} [{task.status}] {task.description} "
            f"(agent_model={task.agent_model or load_config()['agent_model']})"
        )


@queue.command()
@click.option("--concurrency", default=1, show_default=True, type=int)
def run(concurrency: int) -> None:
    """Process tasks with the configured agent workforce."""
    init_logging()
    run_task_loop(concurrency=concurrency)


@cli.group()
def agent() -> None:
    """Agent workforce helpers."""


@agent.command()
@click.argument("number", type=int)
@click.option("--model", default=None, help="Override agent model for this run.")
def spawn(number: int, model: Optional[str]) -> None:
    """Spawn worker agents to pull from the queue."""
    init_logging()
    run_task_loop(concurrency=number, agent_model=model)


@agent.group()
def model() -> None:
    """Agent model controls."""


@model.command("show")
def agent_model_show() -> None:
    """Show the current workforce model."""
    config = load_config()
    click.echo(config["agent_model"])


@model.command("set")
@click.argument("model_name")
def agent_model_set(model_name: str) -> None:
    """Set the workforce model for spawned agents."""
    set_agent_model(model_name)
    click.echo(f"Agent workforce model set to {model_name}")


@cli.group()
def schedule() -> None:
    """Scheduling helpers."""


@schedule.command()
@click.argument("task_description")
@click.argument("when")
def add(task_description: str, when: str) -> None:
    """Schedule a task for later execution."""
    parsed = parse_schedule_time(when)
    task_id = add_scheduled_task(task_description, parsed)
    click.echo(f"Scheduled task {task_id} for {parsed.isoformat()}")


@schedule.command()
@click.option("--poll", type=int, default=None, help="Override poll interval in seconds.")
@click.option("--once", is_flag=True, help="Run a single release cycle and exit.")
def run(poll: Optional[int], once: bool) -> None:
    """Run the scheduling loop."""
    run_schedule_loop(poll_seconds=poll, once=once)


@cli.command()
def monitor() -> None:
    """Display current queue statistics."""
    store = TaskStore(get_paths()["task_db"])
    try:
        stats = store.stats()
    finally:
        store.close()
    click.echo("Queue status:")
    for key, value in stats.items():
        click.echo(f"- {key}: {value}")


@cli.command()
def status() -> None:
    """Print the current configuration state."""
    click.echo(export_state())


if __name__ == "__main__":
    cli()
