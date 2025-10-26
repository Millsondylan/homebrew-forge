"""
Task queue management.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from . import constants
from .config import get_runtime_settings, load_config
from .logger import write_agent_log, write_system_log
from .runtime.dispatcher import AgentDispatcher


CREATE_TASKS_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    agent_model TEXT,
    result TEXT
);
"""

CREATE_SCHEDULE_SQL = """
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    scheduled_for TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);
"""


@dataclass
class Task:
    id: int
    description: str
    status: str
    created_at: datetime
    updated_at: datetime
    agent_model: Optional[str]
    result: Optional[str]


class TaskStore:
    """Thread-safe wrapper for the SQLite task store."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._bootstrap()

    def _bootstrap(self) -> None:
        self.conn.execute(CREATE_TASKS_SQL)
        self.conn.execute(CREATE_SCHEDULE_SQL)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def add_task(self, description: str, agent_model: Optional[str] = None) -> int:
        now = datetime.utcnow().isoformat()
        with self.lock:
            cur = self.conn.execute(
                """
                INSERT INTO tasks (description, status, created_at, updated_at, agent_model)
                VALUES (?, 'pending', ?, ?, ?)
                """,
                (description, now, now, agent_model),
            )
            self.conn.commit()
            task_id = cur.lastrowid
        write_system_log(f"Task {task_id} added: {description}")
        return task_id

    def list_tasks(self, limit: Optional[int] = None) -> List[Task]:
        query = "SELECT id, description, status, created_at, updated_at, agent_model, result FROM tasks ORDER BY id"
        if limit:
            query += f" LIMIT {int(limit)}"
        cur = self.conn.execute(query)
        return [
            Task(
                id=row["id"],
                description=row["description"],
                status=row["status"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                agent_model=row["agent_model"],
                result=row["result"],
            )
            for row in cur.fetchall()
        ]

    def claim_task(self) -> Optional[Task]:
        with self.lock:
            cur = self.conn.execute(
                """
                SELECT id, description, status, created_at, updated_at, agent_model, result
                FROM tasks
                WHERE status = 'pending'
                ORDER BY id
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                return None
            now = datetime.utcnow().isoformat()
            self.conn.execute(
                "UPDATE tasks SET status = 'running', updated_at = ? WHERE id = ?",
                (now, row["id"]),
            )
            self.conn.commit()
        return Task(
            id=row["id"],
            description=row["description"],
            status="running",
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(now),
            agent_model=row["agent_model"],
            result=row["result"],
        )

    def complete_task(self, task_id: int, result: str) -> None:
        now = datetime.utcnow().isoformat()
        with self.lock:
            self.conn.execute(
                "UPDATE tasks SET status = 'completed', updated_at = ?, result = ? WHERE id = ?",
                (now, result, task_id),
            )
            self.conn.commit()

    def fail_task(self, task_id: int, reason: str) -> None:
        now = datetime.utcnow().isoformat()
        with self.lock:
            self.conn.execute(
                "UPDATE tasks SET status = 'failed', updated_at = ?, result = ? WHERE id = ?",
                (now, reason, task_id),
            )
            self.conn.commit()

    def add_scheduled_task(self, description: str, scheduled_for: datetime) -> int:
        now = datetime.utcnow().isoformat()
        with self.lock:
            cur = self.conn.execute(
                """
                INSERT INTO scheduled_tasks (description, scheduled_for, created_at, status)
                VALUES (?, ?, ?, 'pending')
                """,
                (description, scheduled_for.isoformat(), now),
            )
            self.conn.commit()
            task_id = cur.lastrowid
        write_system_log(f"Scheduled task {task_id} for {scheduled_for.isoformat()}: {description}")
        return task_id

    def release_due_scheduled(self, limit: Optional[int] = None) -> int:
        now = datetime.utcnow().isoformat()
        with self.lock:
            cur = self.conn.execute(
                """
                SELECT id, description FROM scheduled_tasks
                WHERE status = 'pending' AND scheduled_for <= ?
                ORDER BY scheduled_for
                """,
                (now,),
            )
            rows = cur.fetchall()
            if not rows:
                return 0
            count = 0
            for row in rows:
                self.conn.execute(
                    "UPDATE scheduled_tasks SET status = 'released' WHERE id = ?",
                    (row["id"],),
                )
                self.conn.execute(
                    """
                    INSERT INTO tasks (description, status, created_at, updated_at)
                    VALUES (?, 'pending', ?, ?)
                    """,
                    (row["description"], now, now),
                )
                count += 1
                if limit and count >= limit:
                    break
            self.conn.commit()
        if count:
            write_system_log(f"Released {count} scheduled task(s)")
        return count

    def stats(self) -> Dict[str, int]:
        with self.lock:
            total = self.conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            pending = self.conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 'pending'"
            ).fetchone()[0]
            running = self.conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 'running'"
            ).fetchone()[0]
            completed = self.conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 'completed'"
            ).fetchone()[0]
            failed = self.conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 'failed'"
            ).fetchone()[0]
        return {
            "total": total,
            "pending": pending,
            "running": running,
            "completed": completed,
            "failed": failed,
        }

    def pending_count(self) -> int:
        with self.lock:
            return self.conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'").fetchone()[0]


def run_task_loop(concurrency: int, agent_model: Optional[str] = None, autoscale: Optional[bool] = None) -> None:
    constants.refresh_paths()
    store = TaskStore(constants.TASK_DB)
    config = load_config()
    agent_defaults = config.get("models", {}).get("agent", {})
    resolved_model = agent_model or agent_defaults.get("name", config["agent_model"])
    runtime = get_runtime_settings()
    autoscale_cfg = runtime.get("autoscale", {})
    autoscale_enabled = autoscale if autoscale is not None else autoscale_cfg.get("enabled", True)
    autoscale_state = AgentDispatcher._build_autoscale_state(runtime) if autoscale_enabled else None

    dispatcher = AgentDispatcher(
        store=store,
        agent_model=resolved_model,
        process=_process_task,
        initial_concurrency=concurrency or runtime.get("default_concurrency", 10),
        autoscale=autoscale_state,
    )

    try:
        dispatcher.run()
    finally:
        store.close()
        write_system_log("Queue run completed.")


def _process_task(worker_id: int, store: TaskStore, task: Task, agent_model: str) -> None:
    """Simulate task execution with verification steps."""
    write_agent_log(worker_id, f"Task {task.id}: Execution started")
    # Simulate work
    time.sleep(0.5)
    # Logical verification
    logical_ok = bool(task.description.strip())
    write_agent_log(worker_id, f"Task {task.id}: Logical verification {'PASSED' if logical_ok else 'FAILED'}")
    if not logical_ok:
        store.fail_task(task.id, "Logical verification failed: empty description")
        write_agent_log(worker_id, f"Task {task.id}: Aborted due to failed logical verification")
        return
    # Empirical verification (simulated)
    time.sleep(0.2)
    empirical_ok = True
    write_agent_log(worker_id, f"Task {task.id}: Empirical verification {'PASSED' if empirical_ok else 'FAILED'}")

    if empirical_ok:
        result_message = f"Completed with {agent_model}"
        store.complete_task(task.id, result_message)
        write_agent_log(worker_id, f"Task {task.id}: PASSED ✔ ({result_message})")
    else:  # pragma: no cover
        store.fail_task(task.id, "Empirical verification failed")
        write_agent_log(worker_id, f"Task {task.id}: FAILED during empirical verification")
