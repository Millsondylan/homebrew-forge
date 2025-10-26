"""
Configuration helpers for AgentForge CLI.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import yaml

from .constants import (
    AGENT_LOG_TEMPLATE,
    CONFIG_FILE,
    CONFIG_ROOT,
    DATA_DIR,
    DEFAULT_MODELS,
    LOG_DIR,
    TASK_DB,
    SYSTEM_LOG_FILE,
    ANTHROPIC_LOGIN_URL,
)


DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "0.2.0",
    "active_model": DEFAULT_MODELS[0],
    "agent_model": DEFAULT_MODELS[1],
    "available_models": DEFAULT_MODELS,
    "anthropic_login_url": ANTHROPIC_LOGIN_URL,
    "last_login": None,
    "keys": {},
}


def ensure_directories() -> None:
    """Ensure the configuration directories exist."""
    for path in (CONFIG_ROOT, DATA_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)


def load_config() -> Dict[str, Any]:
    """Load configuration or initialize defaults."""
    ensure_directories()
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open("r", encoding="utf-8") as fh:
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
    with CONFIG_FILE.open("w", encoding="utf-8") as fh:
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
        "config_root": CONFIG_ROOT,
        "config_file": CONFIG_FILE,
        "data_dir": DATA_DIR,
        "task_db": TASK_DB,
        "log_dir": LOG_DIR,
        "system_log": SYSTEM_LOG_FILE,
        "agent_log_template": AGENT_LOG_TEMPLATE,
    }


def export_state() -> str:
    """Return a JSON dump of the current configuration (excluding secrets)."""
    config = load_config()
    sanitized = {k: v for k, v in config.items() if k != "keys"}
    return json.dumps(sanitized, indent=2)
