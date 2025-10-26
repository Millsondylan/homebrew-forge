"""
Constants used across the AgentForge CLI.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

# Default configuration paths
CONFIG_ROOT = Path.home() / ".agentforge"
CONFIG_FILE = CONFIG_ROOT / "config.yaml"
DATA_DIR = CONFIG_ROOT / "data"
LOG_DIR = CONFIG_ROOT / "logs"
AGENT_LOG_TEMPLATE = LOG_DIR / "agent_{agent_id}.log"
SYSTEM_LOG_FILE = LOG_DIR / "system.log"
TASK_DB = DATA_DIR / "tasks.db"

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
MANIFEST_FILE = CONFIG_ROOT / "manifest.log"
