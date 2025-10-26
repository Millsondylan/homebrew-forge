"""
Command-line interface for AgentForge.
"""

from __future__ import annotations

import shutil
import subprocess
import webbrowser
from datetime import datetime
from typing import Optional

import click
from .config import (
    ensure_directories,
    record_login,
    set_active_model,
    set_agent_model,
    store_key,
    export_state,
)
from .app import ForgeApp
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


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(get_version(), prog_name="AgentForge")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """AgentForge CLI."""
    if ctx.obj is None or not isinstance(ctx.obj, ForgeApp):
        ctx.obj = ForgeApp.bootstrap()


@cli.command()
@click.pass_obj
def init(app: ForgeApp) -> None:
    """Initialise configuration, database, and log folders."""
    ensure_directories()
    store = TaskStore(app.paths["task_db"])
    store.close()
    app.refresh()
    click.echo(f"Configuration ready at {app.paths['config_root']}")


@cli.group()
@click.pass_context
def auth(ctx: click.Context) -> None:
    """Authentication helpers."""
    if ctx.obj is None or not isinstance(ctx.obj, ForgeApp):
        ctx.obj = ForgeApp.bootstrap()


@auth.command()
@click.pass_obj
def anthropic(app: ForgeApp) -> None:
    """Launch browser login for Anthropic."""
    anthropic_cli = shutil.which("anthropic")
    if anthropic_cli:
        click.echo("Starting Anthropic CLI login flow…")
        try:
            subprocess.run([anthropic_cli, "login"], check=True)
            record_login(datetime.utcnow())
            write_system_log("Anthropic CLI login completed")
            click.echo("Anthropic login completed. Credentials cached by Anthropic tooling.")
            app.refresh()
            return
        except subprocess.CalledProcessError as exc:  # pragma: no cover - external dependency
            write_system_log(f"Anthropic CLI login failed: {exc}")
            click.echo("Anthropic CLI login failed, falling back to direct browser flow.")
    login_url = app.config.get("anthropic_login_url", ANTHROPIC_LOGIN_URL)
    click.echo("Opening browser for Anthropic login…")
    webbrowser.open(login_url, new=1)
    record_login(datetime.utcnow())
    app.refresh()
    write_system_log("Anthropic login triggered via direct browser flow")
    click.echo("Complete the Anthropic login in your browser to finish authentication.")


@auth.command()
@click.argument("api_key")
@click.pass_obj
def openai(app: ForgeApp, api_key: str) -> None:
    """Store OpenAI API key."""
    store_key("openai", api_key)
    app.refresh()
    click.echo("OpenAI key saved.")


@auth.command()
@click.argument("api_key")
@click.pass_obj
def gemini(app: ForgeApp, api_key: str) -> None:
    """Store Gemini API key."""
    store_key("gemini", api_key)
    app.refresh()
    click.echo("Gemini key saved.")


@cli.command(name="/login")
@click.pass_context
def slash_login(ctx: click.Context) -> None:
    """Slash command wrapper for anthropic auth."""
    ctx.invoke(anthropic)


@cli.command(name="/model")
@click.pass_obj
def slash_model(app: ForgeApp) -> None:
    """Slash command to pick the primary model."""
    models = app.config.get("available_models", DEFAULT_MODELS)
    chosen = _prompt_model_choice(models, "models")
    set_active_model(chosen)
    app.refresh()
    click.echo(f"Primary model set to {chosen}")


@cli.command(name="/agentmodel")
@click.pass_obj
def slash_agent_model(app: ForgeApp) -> None:
    """Slash command to update the workforce agent model."""
    models = app.config.get("available_models", DEFAULT_MODELS)
    chosen = _prompt_model_choice(models, "agent models")
    set_agent_model(chosen)
    app.refresh()
    click.echo(f"Agent workforce model set to {chosen}")


@cli.group()
@click.pass_context
def model(ctx: click.Context) -> None:
    """Model management."""
    if ctx.obj is None or not isinstance(ctx.obj, ForgeApp):
        ctx.obj = ForgeApp.bootstrap()


@model.command()
@click.pass_obj
def list(app: ForgeApp) -> None:  # type: ignore[override]
    """List available models."""
    active = app.config["active_model"]
    agent_model = app.config["agent_model"]
    for model_name in app.config["available_models"]:
        marker = []
        if model_name == active:
            marker.append("active")
        if model_name == agent_model:
            marker.append("agent")
        suffix = f" ({', '.join(marker)})" if marker else ""
        click.echo(f"- {model_name}{suffix}")


@model.command()
@click.argument("model_name")
@click.pass_obj
def set(app: ForgeApp, model_name: str) -> None:
    """Set the active model."""
    set_active_model(model_name)
    app.refresh()
    click.echo(f"Primary model set to {model_name}")


@model.command()
@click.pass_context
def select(ctx: click.Context) -> None:
    """Interactive selection of the active model."""
    ctx.invoke(slash_model)


@cli.group()
@click.pass_context
def queue(ctx: click.Context) -> None:
    """Task queue operations."""
    if ctx.obj is None or not isinstance(ctx.obj, ForgeApp):
        ctx.obj = ForgeApp.bootstrap()


@queue.command()
@click.argument("task_description")
@click.option("--agent-model", "agent_model", default=None, help="Override agent model for this task.")
@click.pass_obj
def add(app: ForgeApp, task_description: str, agent_model: Optional[str]) -> None:
    """Add a task to the queue."""
    store = TaskStore(app.paths["task_db"])
    try:
        task_id = store.add_task(task_description, agent_model)
        click.echo(f"Task {task_id} added.")
    finally:
        store.close()


@queue.command()
@click.option("--limit", default=None, type=int, help="Limit number of tasks listed.")
@click.pass_obj
def list(app: ForgeApp, limit: Optional[int]) -> None:  # type: ignore[override]
    """List tasks in the queue."""
    store = TaskStore(app.paths["task_db"])
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
            f"(agent_model={task.agent_model or app.config['agent_model']})"
        )


@queue.command()
@click.option("--concurrency", default=1, show_default=True, type=int)
@click.pass_obj
def run(app: ForgeApp, concurrency: int) -> None:
    """Process tasks with the configured agent workforce."""
    init_logging()
    run_task_loop(concurrency=concurrency)


@cli.group()
@click.pass_context
def agent(ctx: click.Context) -> None:
    """Agent workforce helpers."""
    if ctx.obj is None or not isinstance(ctx.obj, ForgeApp):
        ctx.obj = ForgeApp.bootstrap()


@agent.command()
@click.argument("number", type=int)
@click.option("--model", default=None, help="Override agent model for this run.")
@click.pass_obj
def spawn(app: ForgeApp, number: int, model: Optional[str]) -> None:
    """Spawn worker agents to pull from the queue."""
    init_logging()
    run_task_loop(concurrency=number, agent_model=model)


@agent.group()
@click.pass_context
def model(ctx: click.Context) -> None:
    """Agent model controls."""
    if ctx.obj is None or not isinstance(ctx.obj, ForgeApp):
        ctx.obj = ForgeApp.bootstrap()


@model.command("show")
@click.pass_obj
def agent_model_show(app: ForgeApp) -> None:
    """Show the current workforce model."""
    click.echo(app.config["agent_model"])


@model.command("set")
@click.argument("model_name")
@click.pass_obj
def agent_model_set(app: ForgeApp, model_name: str) -> None:
    """Set the workforce model for spawned agents."""
    set_agent_model(model_name)
    app.refresh()
    click.echo(f"Agent workforce model set to {model_name}")


@cli.group()
@click.pass_context
def schedule(ctx: click.Context) -> None:
    """Scheduling helpers."""
    if ctx.obj is None or not isinstance(ctx.obj, ForgeApp):
        ctx.obj = ForgeApp.bootstrap()


@schedule.command()
@click.argument("task_description")
@click.argument("when")
@click.pass_obj
def add(app: ForgeApp, task_description: str, when: str) -> None:
    """Schedule a task for later execution."""
    parsed = parse_schedule_time(when)
    task_id = add_scheduled_task(task_description, parsed)
    click.echo(f"Scheduled task {task_id} for {parsed.isoformat()}")


@schedule.command()
@click.option("--poll", type=int, default=None, help="Override poll interval in seconds.")
@click.option("--once", is_flag=True, help="Run a single release cycle and exit.")
@click.pass_obj
def run(app: ForgeApp, poll: Optional[int], once: bool) -> None:
    """Run the scheduling loop."""
    run_schedule_loop(poll_seconds=poll, once=once)


@cli.command()
@click.pass_obj
def monitor(app: ForgeApp) -> None:
    """Display current queue statistics."""
    store = TaskStore(app.paths["task_db"])
    try:
        stats = store.stats()
    finally:
        store.close()
    click.echo("Queue status:")
    for key, value in stats.items():
        click.echo(f"- {key}: {value}")


@cli.command()
@click.pass_obj
def status(app: ForgeApp) -> None:
    """Print the current configuration state."""
    app.refresh()
    click.echo(export_state())


if __name__ == "__main__":
    cli()
