"""Runtime event helpers for agent broadcasts."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .. import constants
from ..logger import write_system_log


def broadcast_model_change(kind: str, provider: str, model: str) -> None:
    timestamp = datetime.utcnow().isoformat()
    message = f"Model change broadcast [{kind}] -> {provider}:{model} at {timestamp}"
    write_system_log(message)
    constants.refresh_paths()
    events_dir = constants.DATA_DIR
    events_dir.mkdir(parents=True, exist_ok=True)
    payload = {"timestamp": timestamp, "kind": kind, "provider": provider, "model": model}
    events_file = events_dir / "model_events.log"
    with events_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload) + "\n")


__all__ = ["broadcast_model_change"]
