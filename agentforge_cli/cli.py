"""
Command-line interface for AgentForge.
"""

from __future__ import annotations

import json
import shutil
import time
import webbrowser
from datetime import datetime
from pathlib import Path
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
from .dashboard import run_dashboard
from .logger import init_logging, write_system_log
from .memory import default_memory_store
from .queue import TaskStore, run_task_loop
from .scheduler import add_scheduled_task, parse_schedule_time, run_schedule_loop
from . import get_version
from .oauth.flow import perform_pkce_oauth
from .runtime.events import broadcast_model_change
from .verification import export_verification_report
from .reports import generate_final_report


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


@auth.command("cto-new")
@click.option("--session-id", required=False, help="Session identifier from cto.new cookie.")
@click.option("--cookie", required=False, help="Value of the __Secure-next-auth.session-token cookie.")
@click.option("--organization-id", required=False, help="Organization ID from the cto.new API response.")
@click.option("--browser", is_flag=True, help="Open the cto.new login page in your browser.")
@click.pass_obj
def auth_cto_new(
    app: ForgeApp,
    session_id: Optional[str],
    cookie: Optional[str],
    organization_id: Optional[str],
    browser: bool,
) -> None:
    """Configure cto.new credentials."""
    if browser:
        webbrowser.open("https://cto.new/login", new=1)
        click.echo("Complete the login in your browser, then supply session details with --session-id/--cookie/--organization-id.")

    if not (session_id and cookie and organization_id):
        if browser:
            return
        raise click.UsageError("Provide --session-id, --cookie, and --organization-id or use --browser to launch login.")

    manager = app.auth()
    provider = manager.provider("cto_new")
    provider.store_session_tokens(
        manager.store,  # type: ignore[attr-defined]
        session_id=session_id,
        cookie=cookie,
        organization_id=organization_id,
    )
    app.refresh()
    write_system_log("cto.new session tokens stored securely.")
    click.echo("cto.new session tokens stored.")


@cli.command(name="/login")
@click.pass_context
def slash_login(ctx: click.Context) -> None:
    """Slash command wrapper for anthropic auth."""
    ctx.invoke(anthropic, oauth=True)


@cli.command(name="/new")
@click.pass_obj
def slash_new(app: ForgeApp) -> None:
    """Clear the cnovo workspace directory."""
    path = app.paths["cnovo_dir"]
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    click.echo(f"Reset workspace at {path}")


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
@click.option("--idempotency-key", default=None, help="Prevent duplicate enqueue with the same key.")
@click.option("--max-attempts", default=3, type=int, show_default=True, help="Maximum retry attempts before marking failed.")
@click.option("--priority", default=0, type=int, show_default=True, help="Higher values run sooner.")
@click.pass_obj
def add(
    app: ForgeApp,
    task_description: str,
    agent_model: Optional[str],
    idempotency_key: Optional[str],
    max_attempts: int,
    priority: int,
) -> None:
    """Add a task to the queue."""
    store = TaskStore(app.paths["task_db"])
    try:
        task_id = store.add_task(
            task_description,
            agent_model,
            idempotency_key=idempotency_key,
            max_attempts=max_attempts,
            priority=priority,
        )
        click.echo(f"Task {task_id} added." if idempotency_key is None else f"Task {task_id} ready (idempotency applied)")
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
        available = task.available_at.isoformat()
        now = datetime.utcnow()
        delay_suffix = "" if task.available_at <= now else f" (delayed until {available})"
        click.echo(
            f"#{task.id} [{task.status}] {task.description} "
            f"(agent_model={task.agent_model or app.config.get('models', {}).get('agent', {}).get('name', app.config['agent_model'])}, "
            f"attempts={task.attempts}/{task.max_attempts}, priority={task.priority}){delay_suffix}"
        )


@queue.command()
@click.option("--concurrency", default=None, type=int, help="Target worker count (defaults to runtime setting).")
@click.option("--autoscale/--no-autoscale", default=None, help="Enable or disable autoscaling for this run.")
@click.pass_obj
def run(app: ForgeApp, concurrency: Optional[int], autoscale: Optional[bool]) -> None:
    """Process tasks with the configured agent workforce."""
    init_logging()
    runtime = app.config.get("runtime", {})
    target = concurrency or runtime.get("default_concurrency", 10)
    run_task_loop(concurrency=target, autoscale=autoscale)


@cli.group()
@click.pass_context
def agent(ctx: click.Context) -> None:
    """Agent workforce helpers."""
    if ctx.obj is None or not isinstance(ctx.obj, ForgeApp):
        ctx.obj = ForgeApp.bootstrap()


@agent.command()
@click.argument("number", type=int)
@click.option("--model", default=None, help="Override agent model for this run.")
@click.option("--autoscale", is_flag=True, help="Enable autoscaling up to the configured maximum.")
@click.pass_obj
def spawn(app: ForgeApp, number: int, model: Optional[str], autoscale: bool) -> None:
    """Spawn worker agents to pull from the queue."""
    init_logging()
    runtime = app.config.get("runtime", {})
    target = number or runtime.get("default_concurrency", 10)
    run_task_loop(concurrency=target, agent_model=model, autoscale=autoscale)


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
@click.argument("when", required=False)
@click.option("--cron", "cron_expression", default=None, help="Cron expression for recurring schedule.")
@click.option("--timezone", default="UTC", show_default=True, help="Timezone for parsing ISO or cron triggers.")
@click.option("--max-runs", type=int, default=None, help="Maximum runs for a cron schedule before completion.")
@click.pass_obj
def add(
    app: ForgeApp,
    task_description: str,
    when: Optional[str],
    cron_expression: Optional[str],
    timezone: str,
    max_runs: Optional[int],
) -> None:
    """Schedule a task for later execution."""
    spec = parse_schedule_time(when, cron=cron_expression, tz=timezone, max_runs=max_runs)
    task_id = add_scheduled_task(task_description, spec)
    suffix = f" (cron: {spec.cron_expression})" if spec.cron_expression else ""
    click.echo(f"Scheduled task {task_id} for {spec.run_at.isoformat()}{suffix}")


@schedule.command()
@click.option("--poll", type=int, default=None, help="Override poll interval in seconds.")
@click.option("--once", is_flag=True, help="Run a single release cycle and exit.")
@click.pass_obj
def run(app: ForgeApp, poll: Optional[int], once: bool) -> None:
    """Run the scheduling loop."""
    run_schedule_loop(poll_seconds=poll, once=once)


@cli.group()
@click.pass_context
def memory(ctx: click.Context) -> None:
    """Agent memory operations."""
    if ctx.obj is None or not isinstance(ctx.obj, ForgeApp):
        ctx.obj = ForgeApp.bootstrap()


@memory.command()
@click.argument("query")
@click.option("--limit", default=5, show_default=True, type=int)
@click.option("--agent-id", default=None, help="Filter by agent identifier.")
@click.pass_obj
def search(app: ForgeApp, query: str, limit: int, agent_id: Optional[str]) -> None:
    """Search stored agent memories."""
    with default_memory_store() as store:
        results = store.search(query, limit=limit, agent_id=agent_id)
    if not results:
        click.echo("No memories found.")
        return
    click.echo(f"Top {len(results)} memories:")
    for record in results:
        snippet = record.content[:120] + ("…" if len(record.content) > 120 else "")
        click.echo(
            f"- [{record.similarity:.2f}] {record.agent_id} #{record.id} | {snippet}"
        )


@cli.group()
@click.pass_context
def prompt(ctx: click.Context) -> None:
    """Prompt management helpers."""
    if ctx.obj is None or not isinstance(ctx.obj, ForgeApp):
        ctx.obj = ForgeApp.bootstrap()


@prompt.command()
@click.argument("task")
@click.option("--context", multiple=True, help="Additional context lines to include.")
@click.pass_obj
def preview(app: ForgeApp, task: str, context: tuple[str, ...]) -> None:
    """Render the system prompt that will be used for a task."""
    manager = app.prompt_manager()
    rendered = manager.render(task, context=context)
    click.echo(rendered.system_prompt)


@cli.command()
@click.option("--follow/--no-follow", default=False, help="Stream logs and refresh stats continuously.")
@click.option("--interval", default=5.0, show_default=True, type=float, help="Refresh interval in seconds when following.")
@click.pass_obj
def monitor(app: ForgeApp, follow: bool, interval: float) -> None:
    """Display current queue statistics."""

    def print_stats() -> None:
        store = TaskStore(app.paths["task_db"])
        try:
            stats = store.stats()
        finally:
            store.close()
        click.echo("Queue status:")
        for key, value in stats.items():
            click.echo(f"- {key}: {value}")

    def stream_logs(position: int) -> int:
        log_path = app.paths["system_log"]
        if not log_path.exists():
            return position
        with log_path.open("r", encoding="utf-8") as fh:
            fh.seek(position)
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    click.echo(line)
                    continue
                timestamp = payload.get("timestamp", "")
                level = payload.get("level", "INFO")
                message = payload.get("message", "")
                click.echo(f"[{timestamp}] {level}: {message}")
            position = fh.tell()
        return position

    print_stats()
    if not follow:
        return

    click.echo("--- Streaming system log (Ctrl+C to stop) ---")
    position = 0
    try:
        while True:
            position = stream_logs(position)
            time.sleep(max(interval, 0.5))
            print_stats()
    except KeyboardInterrupt:
        click.echo("Stopping monitor.")


@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8765, show_default=True, type=int)
@click.pass_obj
def dashboard(app: ForgeApp, host: str, port: int) -> None:
    """Serve a lightweight dashboard for queue stats and model controls."""
    server = run_dashboard(host, port)
    actual_port = server.server_address[1]
    click.echo(f"Dashboard available at http://{host}:{actual_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo("Shutting down dashboard…")
        server.shutdown()
    finally:
        server.server_close()


@cli.group()
@click.pass_context
def verify(ctx: click.Context) -> None:
    """Verification tooling."""
    if ctx.obj is None or not isinstance(ctx.obj, ForgeApp):
        ctx.obj = ForgeApp.bootstrap()


@verify.command("export")
@click.option("--output", type=click.Path(path_type=Path), default=None, help="Destination file for verification report.")
@click.pass_obj
def verify_export(app: ForgeApp, output: Optional[Path]) -> None:
    """Export accumulated verification results to a timestamped JSON file."""
    report_path = export_verification_report(output)
    click.echo(f"Verification report written to {report_path}")


@verify.command("final-report")
@click.option("--output", type=click.Path(path_type=Path), default=Path("reports/final_verification.json"))
@click.pass_obj
def verify_final_report(app: ForgeApp, output: Path) -> None:
    """Generate the final TODO summary report."""
    report_path = generate_final_report(output)
    click.echo(f"Final verification report written to {report_path}")


@cli.command(name="/")
@click.pass_context
def slash_palette(ctx: click.Context) -> None:
    """Interactive command palette - browse and execute commands."""
    from .palette import execute_command_from_palette

    execute_command_from_palette(ctx.parent.command, ctx)


@cli.command(name="resume")
@click.argument("session_id", required=False)
@click.pass_obj
def resume_command(app: ForgeApp, session_id: Optional[str]) -> None:
    """Resume a previous planning or execution session."""
    from .session import list_sessions, load_session, find_session, get_latest_session

    sessions_dir = app.paths["sessions_dir"]

    # List available sessions
    sessions = list_sessions(sessions_dir)

    if not sessions:
        click.echo("No sessions found.")
        return

    # If no session_id provided, show list and prompt
    if not session_id:
        click.echo("Available sessions:")
        click.echo("")
        for idx, sess in enumerate(sessions, 1):
            status_icon = "✓" if sess["current_phase"] == "completed" else "●"
            click.echo(
                f"  {idx}. {status_icon} {sess['session_id'][:8]}... "
                f"({sess['current_phase']}) - {sess['updated_at']}"
            )
            if sess.get("command"):
                click.echo(f"      Command: {sess['command']}")
            click.echo(f"      TODOs: {sess['completed_todos']}/{sess['todo_count']}")
            click.echo("")

        # Prompt for selection
        choice = click.prompt(
            "Select session number (or Enter for latest)",
            type=str,
            default="",
        )

        if choice == "":
            # Use latest
            latest = get_latest_session(sessions_dir)
            if latest:
                session_id = latest["session_id"]
            else:
                click.echo("No sessions available.")
                return
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(sessions):
                    session_id = sessions[idx]["session_id"]
                else:
                    click.echo("Invalid selection.")
                    return
            except ValueError:
                # Try as session ID or prefix
                found = find_session(choice, sessions_dir)
                if found:
                    session_id = found
                else:
                    click.echo(f"Session not found: {choice}")
                    return

    # Load session
    try:
        session = load_session(session_id, sessions_dir)
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error loading session: {e}")
        return

    # Display session info
    click.echo(f"Resuming session: {session.session_id}")
    click.echo(f"  Created: {session.created_at}")
    click.echo(f"  Updated: {session.updated_at}")
    click.echo(f"  Command: {session.command or 'N/A'}")
    click.echo(f"  Phase: {session.current_phase}")

    progress = session.get_progress()
    click.echo(f"  Progress: {progress['completed']}/{progress['total']} TODOs ({progress['percent']}%)")

    # Display outputs
    if session.outputs:
        click.echo(f"  Outputs:")
        for key, value in session.outputs.items():
            click.echo(f"    - {key}: {value}")

    # Display pending TODOs
    pending = session.get_pending_todos()
    if pending:
        click.echo(f"\nPending TODOs ({len(pending)}):")
        for todo in pending[:5]:
            click.echo(f"  - {todo.id}: {todo.title}")
        if len(pending) > 5:
            click.echo(f"  ... and {len(pending) - 5} more")

    click.echo("\nSession restored successfully!")
    click.echo("You can now continue execution from this checkpoint.")


@cli.command(name="plan")
@click.option("--output-dir", type=click.Path(path_type=Path), default=None, help="Directory to save plan and TODOs.")
@click.pass_obj
def plan_command(app: ForgeApp, output_dir: Optional[Path]) -> None:
    """Generate discovery report, execution plan, and TODOs."""
    from .discovery import discover_codebase, discover_components, generate_discovery_report
    from .planning import generate_plan, format_todos_yaml
    from .session import Session, save_session

    if output_dir is None:
        output_dir = app.paths["docs_dir"]

    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo("Starting discovery phase...")

    # Discovery
    project_root = app.paths["project_root"]

    # Load existing discovery if available
    from .discovery import load_existing_discovery, merge_discovery
    existing_discovery_file = project_root / ".agentforge" / "discovery.json"
    existing_discovery = load_existing_discovery(existing_discovery_file)

    if existing_discovery:
        click.echo(f"  Loaded existing discovery from {existing_discovery_file}")

    discovery_report = generate_discovery_report(
        project_root,
        output_file=output_dir / "discovery.md",
        requirements=["/plan", "/resume", "/"]
    )

    click.echo(f"✓ Discovery complete: {output_dir / 'discovery.md'}")

    # Generate plan
    click.echo("Generating execution plan...")

    # Define feature specifications
    feature_specs = [
        {
            "name": "/plan command",
            "phase": "Plan Command Implementation",
            "description": "Implement automated discovery and planning",
            "components": [
                "Discovery automation module",
                "Planning workflow module",
                "TODO generation system",
                "CLI plan command",
            ]
        },
        {
            "name": "/resume command",
            "phase": "Resume Command Implementation",
            "description": "Implement session restoration",
            "components": [
                "Session scanning",
                "Session selection UI",
                "State restoration",
                "CLI resume command",
            ]
        },
        {
            "name": "/ command palette",
            "phase": "Command Palette Implementation",
            "description": "Implement interactive command browser",
            "components": [
                "Command catalog builder",
                "Interactive selector",
                "Fuzzy search",
                "CLI palette command",
            ]
        },
    ]

    plan_md, todos = generate_plan(
        project_root,
        feature_specs,
        output_dir=output_dir
    )

    click.echo(f"✓ Plan generated: {output_dir / 'plan.md'}")

    # Generate TODOs YAML
    todos_yaml = format_todos_yaml(
        todos,
        project_name="AgentForge",
        target_version="0.4.0",
        output_file=output_dir / "TODOs.yaml"
    )

    click.echo(f"✓ TODOs generated: {output_dir / 'TODOs.yaml'} ({len(todos)} items)")

    # Create session
    session = Session(command="plan", current_phase="planning")
    session.context["project_root"] = str(project_root)
    session.context["output_dir"] = str(output_dir)
    session.outputs["discovery_report"] = str(output_dir / "discovery.md")
    session.outputs["plan_file"] = str(output_dir / "plan.md")
    session.outputs["todos_file"] = str(output_dir / "TODOs.yaml")

    session_file = save_session(session, app.paths["sessions_dir"])
    click.echo(f"✓ Session saved: {session_file.name}")

    # Summary
    click.echo("")
    click.echo("Plan generation complete!")
    click.echo(f"  - Discovery: {output_dir / 'discovery.md'}")
    click.echo(f"  - Plan: {output_dir / 'plan.md'}")
    click.echo(f"  - TODOs: {output_dir / 'TODOs.yaml'} ({len(todos)} items)")
    click.echo(f"  - Session: {session_file.name}")


@cli.command()
@click.pass_obj
def status(app: ForgeApp) -> None:
    """Print the current configuration state."""
    app.refresh()
    click.echo(export_state())


if __name__ == "__main__":
    cli()
