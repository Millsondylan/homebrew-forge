"""
Logging helpers for AgentForge CLI.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import constants


def init_logging() -> None:
    constants.refresh_paths()
    constants.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(constants.SYSTEM_LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def agent_log_path(agent_id: int) -> Path:
    constants.refresh_paths()
    return Path(str(constants.AGENT_LOG_TEMPLATE).format(agent_id=f"{agent_id:03d}"))


def write_agent_log(agent_id: int, message: str) -> None:
    path = agent_log_path(agent_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().isoformat()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"[{timestamp}] [Agent {agent_id:03d}] {message}\n")


def write_system_log(message: str) -> None:
    constants.refresh_paths()
    constants.LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().isoformat()
    with constants.SYSTEM_LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"[{timestamp}] {message}\n")
