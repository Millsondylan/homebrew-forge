"""
Configuration helpers for AgentForge CLI.
"""

from __future__ import annotations

import json
import os
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import yaml

from . import constants


DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "0.2.0",
    "active_model": constants.DEFAULT_MODELS[0],
    "agent_model": constants.DEFAULT_MODELS[1],
    "available_models": constants.DEFAULT_MODELS,
    "anthropic_login_url": constants.ANTHROPIC_LOGIN_URL,
    "last_login": None,
    "keys": {},
}


def ensure_directories() -> None:
    """Ensure the configuration directories exist."""
    constants.refresh_paths()
    for path in (
        constants.CONFIG_ROOT,
        constants.DATA_DIR,
        constants.LOG_DIR,
        constants.DB_DIR,
        constants.AGENTS_DIR,
        constants.SCHEDULES_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def ensure_env_file() -> None:
    """Create a default .env file for provider credentials if missing."""
    ensure_directories()
    if constants.ENV_FILE.exists():
        return
    timestamp = datetime.utcnow().isoformat() + "Z"
    content = textwrap.dedent(
        f"""\
        # AgentForge environment configuration
        # Generated on {timestamp}
        # Uncomment entries you plan to manage through dotenv workflows.
        # ANTHROPIC_API_KEY=
        # GEMINI_API_KEY=
        # GOOGLE_APPLICATION_CREDENTIALS=
        # OPENAI_API_KEY=
        OLLAMA_BASE_URL=http://localhost:11434
        """
    )
    with constants.ENV_FILE.open("w", encoding="utf-8") as fh:
        fh.write(content)


def load_config() -> Dict[str, Any]:
    """Load configuration or initialize defaults."""
    ensure_directories()
    if constants.CONFIG_FILE.exists():
        with constants.CONFIG_FILE.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    else:
        data = DEFAULT_CONFIG.copy()
        save_config(data)
    # Ensure required keys exist
    merged = DEFAULT_CONFIG.copy()
    merged.update(data)
    return merged


def save_config(config: Dict[str, Any]) -> None:
    """Persist configuration to disk."""
    ensure_directories()
    with constants.CONFIG_FILE.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(config, fh, sort_keys=True)


def record_login(timestamp: datetime | None = None) -> None:
    """Persist the most recent login timestamp."""
    config = load_config()
    config["last_login"] = (timestamp or datetime.utcnow()).isoformat()
    save_config(config)


def set_active_model(model_name: str) -> None:
    config = load_config()
    if model_name not in config["available_models"]:
        raise ValueError(f"Unknown model '{model_name}'.")
    config["active_model"] = model_name
    save_config(config)


def set_agent_model(model_name: str) -> None:
    config = load_config()
    if model_name not in config["available_models"]:
        raise ValueError(f"Unknown model '{model_name}'.")
    config["agent_model"] = model_name
    save_config(config)


def store_key(provider: str, key: str) -> None:
    config = load_config()
    config.setdefault("keys", {})[provider] = key.strip()
    save_config(config)


def get_paths() -> Dict[str, Path]:
    ensure_directories()
    return {
        "config_root": constants.CONFIG_ROOT,
        "config_file": constants.CONFIG_FILE,
        "data_dir": constants.DATA_DIR,
        "db_dir": constants.DB_DIR,
        "task_db": constants.TASK_DB,
        "agents_dir": constants.AGENTS_DIR,
        "log_dir": constants.LOG_DIR,
        "system_log": constants.SYSTEM_LOG_FILE,
        "agent_log_template": constants.AGENT_LOG_TEMPLATE,
        "env_file": constants.ENV_FILE,
        "schedules_dir": constants.SCHEDULES_DIR,
    }


def export_state() -> str:
    """Return a JSON dump of the current configuration (excluding secrets)."""
    config = load_config()
    sanitized = {k: v for k, v in config.items() if k != "keys"}
    return json.dumps(sanitized, indent=2)
