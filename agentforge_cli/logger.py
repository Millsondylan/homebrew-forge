"""Logging helpers for AgentForge CLI."""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from . import constants

MAX_LOG_BYTES = 1_000_000
BACKUP_COUNT = 5


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def init_logging() -> None:
    constants.refresh_paths()
    constants.LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        constants.SYSTEM_LOG_FILE,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(JsonFormatter())
    console = logging.StreamHandler()
    console.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler, console], force=True)


def agent_log_path(agent_id: int) -> Path:
    constants.refresh_paths()
    return Path(str(constants.AGENT_LOG_TEMPLATE).format(agent_id=f"{agent_id:03d}"))


def _rotate_if_needed(path: Path) -> None:
    if not path.exists():
        return
    if path.stat().st_size <= MAX_LOG_BYTES:
        return
    for idx in range(BACKUP_COUNT, 0, -1):
        src = Path(f"{path}.{idx - 1}" if idx > 1 else str(path))
        dest = Path(f"{path}.{idx}")
        if dest.exists():
            dest.unlink()
        if src.exists():
            os.replace(src, dest)


def _append_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _rotate_if_needed(path)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload) + "\n")


def write_agent_log(agent_id: int, message: str, *, extra: Optional[Dict[str, Any]] = None) -> None:
    timestamp = datetime.utcnow().isoformat() + "Z"
    payload: Dict[str, Any] = {
        "timestamp": timestamp,
        "agent_id": f"agent-{agent_id:03d}",
        "message": message,
    }
    if extra:
        payload.update(extra)
    _append_json(agent_log_path(agent_id), payload)


def write_system_log(message: str, *, level: str = "INFO", extra: Optional[Dict[str, Any]] = None) -> None:
    constants.refresh_paths()
    payload: Dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "message": message,
    }
    if extra:
        payload.update(extra)
    _append_json(constants.SYSTEM_LOG_FILE, payload)
