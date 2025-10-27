"""
Configuration helpers for AgentForge CLI.
"""

from __future__ import annotations

import json
import os
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

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
    "providers": {
        "anthropic": {
            "oauth": {
                "authorize_url": "https://console.anthropic.com/oauth/authorize",
                "token_url": "https://api.anthropic.com/oauth/token",
                "client_id": None,
                "scopes": [
                    "org:create_api_key",
                    "user:profile",
                    "user:inference",
                ],
                "extra_params": {
                    "redirect_uri": "https://console.anthropic.com/oauth/code/callback",
                },
            }
        },
        "gemini": {
            "oauth": {
                "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_url": "https://oauth2.googleapis.com/token",
                "client_id": None,
                "scopes": [
                    "https://www.googleapis.com/auth/generative-language.retriever",
                ],
                "extra_params": {
                    "access_type": "offline",
                    "prompt": "consent",
                },
            }
        },
        "ollama": {
            "http": {
                "base_url": "http://localhost:11434",
            }
        },
        "local": {},
        "cto_new": {
            "session": {
                "login_url": "https://cto.new/login",
                "notes": "After logging in, copy the __Secure-next-auth.session-token cookie and session_id from your browser dev tools.",
            }
        },
    },
    "model_catalog": {
        "anthropic": constants.DEFAULT_MODELS,
        "gemini": [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ],
        "ollama": [
            "llama3:70b",
            "llama3:8b",
        ],
        "local": [],
    },
    "models": {
        "primary": {"provider": "anthropic", "name": constants.DEFAULT_MODELS[0]},
        "agent": {"provider": "anthropic", "name": constants.DEFAULT_MODELS[1]},
    },
    "runtime": {
        "default_concurrency": 10,
        "max_concurrency": 500,
        "autoscale": {
            "enabled": True,
            "scale_up_pending_per_worker": 2,
            "scale_down_idle_cycles": 3,
        },
    },
    "prompts": {
        "base": (
            "You are an AgentForge autonomous developer."
            "\nTask: {task_description}\n"
            "\nDiscipline Rules:\n{rules}\n"
            "\nRelevant Memory:\n{context}\n"
            "\nVerification Plan:\n{verification}\n"
        ),
        "rules": [
            "Truth Over Comfort — never omit or fabricate facts.",
            "Full Completion — deliver end-to-end results with evidence.",
            "Double Verification — run logical checks and empirical validation for every outcome.",
            "Persistent Logging — record actions, decisions, and verification output.",
            "Escalate Uncertainty — surface blockers immediately instead of guessing.",
        ],
        "default_verification": [
            "Run logical assertions covering critical branches.",
            "Execute empirical validation (tests, scripts, or external calls) and record evidence.",
        ],
    },
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
        constants.CNOVO_DIR,
        constants.DOCS_DIR,
        constants.SESSIONS_DIR,
        constants.PROJECT_LOG_DIR,
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
    merged.setdefault("model_catalog", DEFAULT_CONFIG["model_catalog"].copy())
    merged.setdefault("models", DEFAULT_CONFIG["models"].copy())
    for key in ("primary", "agent"):
        merged["models"].setdefault(key, DEFAULT_CONFIG["models"][key].copy())
    runtime_default = DEFAULT_CONFIG["runtime"].copy()
    runtime_default["autoscale"] = DEFAULT_CONFIG["runtime"]["autoscale"].copy()
    merged.setdefault("runtime", runtime_default)
    merged["runtime"].setdefault("autoscale", runtime_default["autoscale"].copy())
    prompts_default = DEFAULT_CONFIG["prompts"].copy()
    prompts_default["rules"] = DEFAULT_CONFIG["prompts"]["rules"].copy()
    prompts_default["default_verification"] = DEFAULT_CONFIG["prompts"]["default_verification"].copy()
    merged.setdefault("prompts", prompts_default)
    merged["prompts"].setdefault("rules", prompts_default["rules"])
    merged["prompts"].setdefault("default_verification", prompts_default["default_verification"])
    merged["prompts"].setdefault("base", prompts_default["base"])
    return merged
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


def _ensure_model_available(config: Dict[str, Any], provider: str, model_name: str) -> None:
    catalog = config.get("model_catalog", {})
    options = catalog.get(provider, [])
    if model_name not in options:
        raise ValueError(f"Unknown model '{model_name}' for provider '{provider}'.")


def set_active_model(model_name: str, provider: Optional[str] = None) -> None:
    config = load_config()
    chosen_provider = provider or config.get("models", {}).get("primary", {}).get("provider", "anthropic")
    _ensure_model_available(config, chosen_provider, model_name)
    config.setdefault("models", {})["primary"] = {"provider": chosen_provider, "name": model_name}
    config["active_model"] = model_name
    save_config(config)


def set_agent_model(model_name: str, provider: Optional[str] = None) -> None:
    config = load_config()
    chosen_provider = provider or config.get("models", {}).get("agent", {}).get("provider", "anthropic")
    _ensure_model_available(config, chosen_provider, model_name)
    config.setdefault("models", {})["agent"] = {"provider": chosen_provider, "name": model_name}
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
        "credentials_file": constants.CREDENTIALS_FILE,
        "credential_key_file": constants.CREDENTIAL_KEY_FILE,
        "memory_db": constants.MEMORY_DB,
        "cnovo_dir": constants.CNOVO_DIR,
        "project_root": constants.PROJECT_ROOT,
        "docs_dir": constants.DOCS_DIR,
        "sessions_dir": constants.SESSIONS_DIR,
        "project_log_dir": constants.PROJECT_LOG_DIR,
        "plan_file": constants.PLAN_FILE,
        "discovery_file": constants.DISCOVERY_FILE,
        "todos_file": constants.TODOS_FILE,
    }


def get_runtime_settings() -> Dict[str, Any]:
    config = load_config()
    runtime = config.get("runtime", {}).copy()
    runtime.setdefault("default_concurrency", 10)
    runtime.setdefault("max_concurrency", 500)
    autoscale = runtime.get("autoscale", {}).copy()
    autoscale.setdefault("enabled", True)
    autoscale.setdefault("scale_up_pending_per_worker", 2)
    autoscale.setdefault("scale_down_idle_cycles", 3)
    runtime["autoscale"] = autoscale
    return runtime


def export_state() -> str:
    """Return a JSON dump of the current configuration (excluding secrets)."""
    config = load_config()
    sanitized = {k: v for k, v in config.items() if k != "keys"}
    return json.dumps(sanitized, indent=2)
