"""Minimal web dashboard for AgentForge status and controls."""

from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Tuple
from urllib.parse import parse_qs, urlparse

from . import constants
from .config import load_config, set_active_model, set_agent_model
from .logger import write_system_log
from .queue import TaskStore


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/model" and parsed.query:
            self._handle_model_update(parse_qs(parsed.query))
            return
        if parsed.path == "/agentmodel" and parsed.query:
            self._handle_agent_model_update(parse_qs(parsed.query))
            return
        self._render_index()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        write_system_log(format % args)

    def _render_index(self) -> None:
        config = load_config()
        store = TaskStore(constants.TASK_DB)
        try:
            stats = store.stats()
        finally:
            store.close()
        html_body = _render_homepage(config, stats)
        body_bytes = html_body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def _handle_model_update(self, params):
        target = params.get("target", [None])[0]
        if target and ":" in target:
            provider, model = target.split(":", 1)
            try:
                set_active_model(model, provider)
                write_system_log(f"Dashboard changed primary model to {provider}:{model}")
            except ValueError as exc:
                write_system_log(f"Dashboard model update failed: {exc}", level="ERROR")
        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()

    def _handle_agent_model_update(self, params):
        target = params.get("target", [None])[0]
        if target and ":" in target:
            provider, model = target.split(":", 1)
            try:
                set_agent_model(model, provider)
                write_system_log(f"Dashboard changed agent model to {provider}:{model}")
            except ValueError as exc:
                write_system_log(f"Dashboard agent model update failed: {exc}", level="ERROR")
        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()


def _render_homepage(config, stats) -> str:
    catalog = config.get("model_catalog", {})
    primary = config.get("models", {}).get("primary", {})
    agent_model = config.get("models", {}).get("agent", {})
    rows = "".join(
        f"<tr><td>{html.escape(key)}</td><td>{value}</td></tr>" for key, value in stats.items()
    )

    def _options(selected_provider: str, selected_model: str) -> str:
        options = []
        for provider, models in catalog.items():
            for model in models:
                selected = " selected" if provider == selected_provider and model == selected_model else ""
                label = html.escape(f"{provider}:{model}")
                options.append(f"<option value='{provider}:{model}'{selected}>{label}</option>")
        return "".join(options)

    primary_options = _options(primary.get("provider", ""), primary.get("name", ""))
    agent_options = _options(agent_model.get("provider", ""), agent_model.get("name", ""))

    return f"""
    <html>
      <head>
        <title>AgentForge Dashboard</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 2rem; }}
          table {{ border-collapse: collapse; margin-top: 1rem; }}
          td, th {{ border: 1px solid #ccc; padding: 0.5rem 1rem; }}
          form {{ margin-top: 1.5rem; }}
        </style>
      </head>
      <body>
        <h1>AgentForge Dashboard</h1>
        <section>
          <h2>Queue Status</h2>
          <table>
            <tbody>
              {rows}
            </tbody>
          </table>
        </section>
        <section>
          <h2>Primary Model</h2>
          <form method="get" action="/model">
            <select name="target" onchange="this.form.submit()">
              {primary_options}
            </select>
          </form>
        </section>
        <section>
          <h2>Agent Workforce Model</h2>
          <form method="get" action="/agentmodel">
            <select name="target" onchange="this.form.submit()">
              {agent_options}
            </select>
          </form>
        </section>
      </body>
    </html>
    """


def run_dashboard(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), DashboardHandler)


__all__ = ["run_dashboard"]
