"""Reporting helpers for AgentForge."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import constants


def generate_final_report(report_path: Optional[Path] = None) -> Path:
    constants.refresh_paths()
    todos_path = Path(".agentforge/todos.json")
    if not todos_path.exists():
        raise FileNotFoundError("TODO tracking file not found.")
    with todos_path.open("r", encoding="utf-8") as fh:
        todos = json.load(fh).get("todos", [])

    if report_path is None:
        report_path = Path("reports/final_verification.json")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "todos": todos,
        "artifacts": [
            str(constants.LOG_DIR / "system.log"),
            str(constants.LOG_DIR / "verification.log"),
            "reports/loadtest.json",
        ],
    }
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return report_path


__all__ = ["generate_final_report"]
