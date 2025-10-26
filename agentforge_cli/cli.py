"""
Command-line interface for AgentForge.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import click
from requests import HTTPError
from .config import (
    ensure_directories,
    ensure_env_file,
    record_login,
    set_active_model,
    set_agent_model,
    store_key,
    export_state,
)
from .app import ForgeApp
from .constants import DEFAULT_MODELS
from .logger import init_logging, write_system_log
from .queue import TaskStore, run_task_loop
from .scheduler import add_scheduled_task, parse_schedule_time, run_schedule_loop
from . import get_version
from .oauth.flow import perform_pkce_oauth
from .runtime.events import broadcast_model_change


def _prompt_model_choice(models: list[str], label: str) -> str:
    click.echo(f"Available {label}:")
    for idx, model in enumerate(models, start=1):
        click.echo(f"  {idx}. {model}")
    choice = click.prompt(f"Select {label} by number", type=click.IntRange(1, len(models)))
    return models[choice - 1]


def _prompt_provider(app: ForgeApp, prompt: str) -> str:
    catalog = app.config.get("model_catalog", {})
    providers = sorted(catalog.keys())
    if not providers:
        raise click.ClickException("No providers defined in model catalog")
    click.echo(prompt)
    for idx, provider in enumerate(providers, start=1):
        click.echo(f"  {idx}. {provider}")
    choice = click.prompt("Select provider", type=click.IntRange(1, len(providers)))
    return providers[choice - 1]


def _parse_provider_model(value: str, fallback_provider: Optional[str]) -> tuple[str, str]:
    if ":" in value:
        provider, model = value.split(":", 1)
        return provider.strip(), model.strip()
    if not fallback_provider:
        raise click.BadParameter("Provider must be specified as provider:model")
    return fallback_provider, value.strip()


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
    ensure_env_file()
    store = TaskStore(app.paths["task_db"])
    store.close()
    app.refresh()
    click.echo("AgentForge workspace initialised:")
    click.echo(f"- config: {app.paths['config_file']}")
    click.echo(f"- env: {app.paths['env_file']}")
    click.echo(f"- agents: {app.paths['agents_dir']}")
    click.echo(f"- database: {app.paths['task_db']}")
    click.echo(f"- logs: {app.paths['log_dir']}")
    click.echo(f"- schedules: {app.paths['schedules_dir']}")


@cli.group()
@click.pass_context
def auth(ctx: click.Context) -> None:
    """Authentication helpers."""
    if ctx.obj is None or not isinstance(ctx.obj, ForgeApp):
        ctx.obj = ForgeApp.bootstrap()


@auth.command()
@click.option("--api-key", "api_key", type=str, help="Store an Anthropic API key.")
@click.option("--oauth", is_flag=True, help="Authenticate with Anthropic OAuth in the browser.")
@click.option("--client-id", type=str, help="Override OAuth client ID.")
@click.option("--redirect-uri", type=str, help="Override OAuth redirect URI.")
@click.option("--no-browser", is_flag=True, help="Do not launch the browser automatically.")
@click.option("--auth-code", type=str, help="Provide an authorization code manually (bypass listener).")
@click.pass_obj
def anthropic(
    app: ForgeApp,
    api_key: Optional[str],
    oauth: bool,
    client_id: Optional[str],
    redirect_uri: Optional[str],
    no_browser: bool,
    auth_code: Optional[str],
) -> None:
    """Manage Anthropic authentication (API key or OAuth)."""

    manager = app.auth()
    action_taken = False

    if api_key:
        manager.store_api_key("anthropic", api_key)
        record_login(datetime.utcnow())
        app.refresh()
        write_system_log("Anthropic API key stored through AgentForge")
        click.echo("Anthropic API key stored securely in the credential vault.")
        action_taken = True

    if oauth:
        action_taken = True
        try:
            metadata = manager.oauth_metadata("anthropic")
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc

        resolved_client_id = client_id or metadata.client_id
        if not resolved_client_id:
            resolved_client_id = click.prompt("Enter the Anthropic OAuth client ID", type=str)

        authorize_extra = dict(metadata.extra_params)
        if redirect_uri:
            authorize_extra.pop("redirect_uri", None)
        else:
            redirect_uri = metadata.extra_params.get("redirect_uri")

        try:
            oauth_payload = perform_pkce_oauth(
                authorize_url=metadata.authorize_url,
                token_url=metadata.token_url,
                client_id=resolved_client_id,
                scopes=metadata.scopes,
                redirect_uri=redirect_uri,
                extra_authorize_params=authorize_extra,
                open_browser=not no_browser,
                manual_code=auth_code,
                audience=metadata.audience,
            )
        except (TimeoutError, ValueError) as exc:
            if auth_code:
                raise click.ClickException(str(exc)) from exc
            click.echo(f"Automatic redirect capture failed: {exc}")
            manual_code = click.prompt("Paste the authorization code provided by Anthropic", type=str)
            oauth_payload = perform_pkce_oauth(
                authorize_url=metadata.authorize_url,
                token_url=metadata.token_url,
                client_id=resolved_client_id,
                scopes=metadata.scopes,
                redirect_uri=redirect_uri,
                extra_authorize_params=authorize_extra,
                open_browser=False,
                manual_code=manual_code,
                audience=metadata.audience,
            )
        except HTTPError as exc:  # pragma: no cover - network errors
            raise click.ClickException(f"Token exchange failed: {exc.response.text if exc.response else exc}") from exc

        manager.persist_oauth_tokens("anthropic", oauth_payload)
        record_login(datetime.utcnow())
        app.refresh()
        write_system_log("Anthropic OAuth tokens stored via AgentForge")
        click.echo("Anthropic OAuth tokens stored. Refresh tokens are encrypted at rest.")

    if not action_taken:
        raise click.UsageError("Specify --api-key or --oauth to select an authentication method.")


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
    ctx.invoke(anthropic, oauth=True)


@cli.command(name="/model")
@click.pass_obj
def slash_model(app: ForgeApp) -> None:
    """Slash command to pick the primary model."""
    provider = _prompt_provider(app, "Select provider for primary model:")
    catalog = app.config.get("model_catalog", {})
    models = catalog.get(provider, DEFAULT_MODELS)
    chosen = _prompt_model_choice(models, f"{provider} models")
    set_active_model(chosen, provider)
    app.refresh()
    broadcast_model_change("primary", provider, chosen)
    click.echo(f"Primary model set to {provider}:{chosen}")


@cli.command(name="/agentmodel")
@click.pass_obj
def slash_agent_model(app: ForgeApp) -> None:
    """Slash command to update the workforce agent model."""
    provider = _prompt_provider(app, "Select provider for agent workforce model:")
    catalog = app.config.get("model_catalog", {})
    models = catalog.get(provider, DEFAULT_MODELS)
    chosen = _prompt_model_choice(models, f"{provider} models")
    set_agent_model(chosen, provider)
    app.refresh()
    broadcast_model_change("agent", provider, chosen)
    click.echo(f"Agent workforce model set to {provider}:{chosen}")


@cli.group()
@click.pass_context
def model(ctx: click.Context) -> None:
    """Model management."""
    if ctx.obj is None or not isinstance(ctx.obj, ForgeApp):
        ctx.obj = ForgeApp.bootstrap()


@model.command()
@click.pass_obj
def list(app: ForgeApp) -> None:  # type: ignore[override]
    """List available models grouped by provider."""
    catalog = app.config.get("model_catalog", {})
    primary = app.config.get("models", {}).get("primary", {})
    agent_model = app.config.get("models", {}).get("agent", {})
    for provider, models in catalog.items():
        click.echo(f"{provider}:")
        for model_name in models:
            marker = []
            if provider == primary.get("provider") and model_name == primary.get("name"):
                marker.append("primary")
            if provider == agent_model.get("provider") and model_name == agent_model.get("name"):
                marker.append("agent")
            suffix = f" ({', '.join(marker)})" if marker else ""
            click.echo(f"  - {model_name}{suffix}")


@model.command()
@click.argument("target")
@click.pass_obj
def set(app: ForgeApp, target: str) -> None:
    """Set the active model using provider:model syntax."""
    current_provider = app.config.get("models", {}).get("primary", {}).get("provider")
    provider, model_name = _parse_provider_model(target, current_provider)
    try:
        set_active_model(model_name, provider)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    app.refresh()
    broadcast_model_change("primary", provider, model_name)
    click.echo(f"Primary model set to {provider}:{model_name}")


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
            f"(agent_model={task.agent_model or app.config.get('models', {}).get('agent', {}).get('name', app.config['agent_model'])})"
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
    agent_cfg = app.config.get("models", {}).get("agent", {})
    provider = agent_cfg.get("provider", "anthropic")
    model_name = agent_cfg.get("name", app.config.get("agent_model"))
    click.echo(f"{provider}:{model_name}")


@model.command("set")
@click.argument("model_name")
@click.pass_obj
def agent_model_set(app: ForgeApp, model_name: str) -> None:
    """Set the workforce model for spawned agents."""
    current_provider = app.config.get("models", {}).get("agent", {}).get("provider")
    provider, resolved = _parse_provider_model(model_name, current_provider)
    try:
        set_agent_model(resolved, provider)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    app.refresh()
    broadcast_model_change("agent", provider, resolved)
    click.echo(f"Agent workforce model set to {provider}:{resolved}")


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
