"""Self-verification helpers for AgentForge agents."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from . import constants


@dataclass
class VerificationResult:
    name: str
    passed: bool
    details: str


class VerificationManager:
    """Record logical and empirical verification events."""

    def __init__(self) -> None:
        constants.refresh_paths()
        self.log_path = constants.LOG_DIR / "verification.log"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, task_id: int, agent_id: str, result: VerificationResult) -> None:
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "task_id": task_id,
            "agent_id": agent_id,
            "check": result.name,
            "passed": result.passed,
            "details": result.details,
        }
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + "\n")

    def logical(self, task_id: int, agent_id: str, description: str) -> VerificationResult:
        passed = bool(description.strip())
        details = "Description present." if passed else "Task description is empty."
        result = VerificationResult(name="logical", passed=passed, details=details)
        self.record(task_id, agent_id, result)
        return result

    def empirical(
        self,
        task_id: int,
        agent_id: str,
        runner: Callable[[], tuple[bool, str]],
    ) -> VerificationResult:
        passed, details = runner()
        result = VerificationResult(name="empirical", passed=passed, details=details)
        self.record(task_id, agent_id, result)
        return result


__all__ = ["VerificationManager", "VerificationResult"]
