"""
Constants used across the AgentForge CLI.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

# Default configuration paths
DEFAULT_CONFIG_ROOT = Path.home() / ".agentforge"
CONFIG_ROOT: Path
CONFIG_FILE: Path
ENV_FILE: Path
AGENTS_DIR: Path
DATA_DIR: Path
DB_DIR: Path
LOG_DIR: Path
SCHEDULES_DIR: Path
AGENT_LOG_TEMPLATE: Path
SYSTEM_LOG_FILE: Path
TASK_DB: Path
CREDENTIALS_FILE: Path
CREDENTIAL_KEY_FILE: Path

# Default Anthropic login URL used to launch the standard Anthropic browser sign-in flow.
ANTHROPIC_LOGIN_URL = "https://console.anthropic.com/login"

# Default model catalog drawn from Anthropic's published Claude 3 family.
DEFAULT_MODELS = [
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
]

# Default retry backoff for schedule runner
SCHEDULE_POLL_INTERVAL = timedelta(seconds=5)

# Persistent manifest metadata
MANIFEST_FILE: Path


def refresh_paths() -> None:
    """Refresh filesystem-derived constants from environment variables."""
    global CONFIG_ROOT, CONFIG_FILE, ENV_FILE, AGENTS_DIR, DATA_DIR, DB_DIR
    global LOG_DIR, SCHEDULES_DIR, AGENT_LOG_TEMPLATE, SYSTEM_LOG_FILE, TASK_DB
    global MANIFEST_FILE, CREDENTIALS_FILE, CREDENTIAL_KEY_FILE

    root = Path(os.environ.get("AGENTFORGE_HOME", str(DEFAULT_CONFIG_ROOT))).expanduser()
    CONFIG_ROOT = root
    CONFIG_FILE = root / "config.yaml"
    ENV_FILE = root / ".env"
    AGENTS_DIR = root / "agents"
    DATA_DIR = root / "data"
    DB_DIR = root / "db"
    LOG_DIR = root / "logs"
    SCHEDULES_DIR = root / "schedules"
    AGENT_LOG_TEMPLATE = LOG_DIR / "agent_{agent_id}.log"
    SYSTEM_LOG_FILE = LOG_DIR / "system.log"
    TASK_DB = DB_DIR / "tasks.db"
    MANIFEST_FILE = root / "manifest.log"
    CREDENTIALS_FILE = root / "credentials.json"
    CREDENTIAL_KEY_FILE = root / ".credentials.key"


refresh_paths()
