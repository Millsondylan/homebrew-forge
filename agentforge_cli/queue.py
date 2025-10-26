"""
Task queue management.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from croniter import croniter

from . import constants
from .config import get_runtime_settings, load_config
from .logger import write_agent_log, write_system_log
from .memory import default_memory_store
from .prompts import default_prompt_manager
from .runtime.dispatcher import AgentDispatcher, AutoscaleState


CREATE_TASKS_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    agent_model TEXT,
    result TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    available_at TEXT NOT NULL DEFAULT (datetime('now')),
    idempotency_key TEXT UNIQUE,
    priority INTEGER NOT NULL DEFAULT 0,
    last_error TEXT
);
"""

CREATE_SCHEDULE_SQL = """
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    scheduled_for TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    cron_expression TEXT,
    timezone TEXT,
    run_count INTEGER NOT NULL DEFAULT 0,
    max_runs INTEGER,
    last_run TEXT
);
"""

CREATE_TASK_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_tasks_pending ON tasks(status, available_at, priority DESC)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_idempotency ON tasks(idempotency_key)",
]


@dataclass
class Task:
    id: int
    description: str
    status: str
    created_at: datetime
    updated_at: datetime
    agent_model: Optional[str]
    result: Optional[str]
    attempts: int
    max_attempts: int
    available_at: datetime
    idempotency_key: Optional[str]
    priority: int
    last_error: Optional[str]


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
        self._ensure_columns()
        self._ensure_schedule_columns()
        for statement in CREATE_TASK_INDEXES:
            self.conn.execute(statement)
        self.conn.commit()

    def _ensure_columns(self) -> None:
        existing = {row[1] for row in self.conn.execute("PRAGMA table_info(tasks)")}
        migrations = []
        if "attempts" not in existing:
            migrations.append("ALTER TABLE tasks ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
        if "max_attempts" not in existing:
            migrations.append("ALTER TABLE tasks ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 3")
        if "available_at" not in existing:
            migrations.append("ALTER TABLE tasks ADD COLUMN available_at TEXT NOT NULL DEFAULT (datetime('now'))")
        if "idempotency_key" not in existing:
            migrations.append("ALTER TABLE tasks ADD COLUMN idempotency_key TEXT")
        if "priority" not in existing:
            migrations.append("ALTER TABLE tasks ADD COLUMN priority INTEGER NOT NULL DEFAULT 0")
        if "last_error" not in existing:
            migrations.append("ALTER TABLE tasks ADD COLUMN last_error TEXT")
        for statement in migrations:
            self.conn.execute(statement)

    def _ensure_schedule_columns(self) -> None:
        existing = {row[1] for row in self.conn.execute("PRAGMA table_info(scheduled_tasks)")}
        migrations = []
        if "cron_expression" not in existing:
            migrations.append("ALTER TABLE scheduled_tasks ADD COLUMN cron_expression TEXT")
        if "timezone" not in existing:
            migrations.append("ALTER TABLE scheduled_tasks ADD COLUMN timezone TEXT")
        if "run_count" not in existing:
            migrations.append("ALTER TABLE scheduled_tasks ADD COLUMN run_count INTEGER NOT NULL DEFAULT 0")
        if "max_runs" not in existing:
            migrations.append("ALTER TABLE scheduled_tasks ADD COLUMN max_runs INTEGER")
        if "last_run" not in existing:
            migrations.append("ALTER TABLE scheduled_tasks ADD COLUMN last_run TEXT")
        for statement in migrations:
            self.conn.execute(statement)

    def close(self) -> None:
        self.conn.close()

    def add_task(
        self,
        description: str,
        agent_model: Optional[str] = None,
        *,
        idempotency_key: Optional[str] = None,
        max_attempts: int = 3,
        priority: int = 0,
        available_at: Optional[datetime] = None,
    ) -> int:
        now = datetime.utcnow()
        available_ts = (available_at or now).isoformat()
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        with self.lock:
            if idempotency_key:
                existing = self.conn.execute(
                    "SELECT id FROM tasks WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
                if existing:
                    return existing[0]
            cur = self.conn.execute(
                """
                INSERT INTO tasks (
                    description,
                    status,
                    created_at,
                    updated_at,
                    agent_model,
                    result,
                    attempts,
                    max_attempts,
                    available_at,
                    idempotency_key,
                    priority,
                    last_error
                )
                VALUES (?, 'pending', ?, ?, ?, NULL, 0, ?, ?, ?, ?, NULL)
                """,
                (
                    description,
                    now.isoformat(),
                    now.isoformat(),
                    agent_model,
                    max_attempts,
                    available_ts,
                    idempotency_key,
                    priority,
                ),
            )
            self.conn.commit()
            task_id = cur.lastrowid
        write_system_log(f"Task {task_id} added: {description}")
        return task_id

    def list_tasks(self, limit: Optional[int] = None) -> List[Task]:
        query = (
            "SELECT id, description, status, created_at, updated_at, agent_model, result, attempts, "
            "max_attempts, available_at, idempotency_key, priority, last_error FROM tasks ORDER BY id"
        )
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
                attempts=row["attempts"],
                max_attempts=row["max_attempts"],
                available_at=datetime.fromisoformat(row["available_at"]),
                idempotency_key=row["idempotency_key"],
                priority=row["priority"],
                last_error=row["last_error"],
            )
            for row in cur.fetchall()
        ]

    def claim_task(self) -> Optional[Task]:
        with self.lock:
            now_iso = datetime.utcnow().isoformat()
            cur = self.conn.execute(
                """
                SELECT id, description, status, created_at, updated_at, agent_model, result,
                       attempts, max_attempts, available_at, idempotency_key, priority, last_error
                FROM tasks
                WHERE status = 'pending' AND available_at <= ?
                ORDER BY priority DESC, available_at ASC, id ASC
                LIMIT 1
                """,
                (now_iso,),
            )
            row = cur.fetchone()
            if not row:
                return None
            new_attempts = row["attempts"] + 1
            self.conn.execute(
                "UPDATE tasks SET status = 'running', updated_at = ?, attempts = ?, last_error = NULL WHERE id = ?",
                (now_iso, new_attempts, row["id"]),
            )
            self.conn.commit()
        return Task(
            id=row["id"],
            description=row["description"],
            status="running",
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(now_iso),
            agent_model=row["agent_model"],
            result=row["result"],
            attempts=new_attempts,
            max_attempts=row["max_attempts"],
            available_at=datetime.fromisoformat(row["available_at"]),
            idempotency_key=row["idempotency_key"],
            priority=row["priority"],
            last_error=row["last_error"],
        )

    def complete_task(self, task_id: int, result: str) -> None:
        now = datetime.utcnow().isoformat()
        with self.lock:
            self.conn.execute(
                "UPDATE tasks SET status = 'completed', updated_at = ?, result = ?, last_error = NULL WHERE id = ?",
                (now, result, task_id),
            )
            self.conn.commit()

    def fail_task(self, task: Task, reason: str) -> None:
        now = datetime.utcnow()
        with self.lock:
            if task.attempts < task.max_attempts:
                delay_seconds = min(2 ** task.attempts, 300)
                available_at = (now + timedelta(seconds=delay_seconds)).isoformat()
                self.conn.execute(
                    """
                    UPDATE tasks
                    SET status = 'pending',
                        updated_at = ?,
                        available_at = ?,
                        last_error = ?,
                        result = NULL
                    WHERE id = ?
                    """,
                    (now.isoformat(), available_at, reason, task.id),
                )
            else:
                self.conn.execute(
                    """
                    UPDATE tasks
                    SET status = 'failed',
                        updated_at = ?,
                        result = ?,
                        last_error = ?
                    WHERE id = ?
                    """,
                    (now.isoformat(), reason, reason, task.id),
                )
            self.conn.commit()

    def add_scheduled_task(
        self,
        description: str,
        scheduled_for: datetime,
        *,
        cron_expression: Optional[str] = None,
        timezone: Optional[str] = None,
        max_runs: Optional[int] = None,
    ) -> int:
        now = datetime.utcnow().isoformat()
        with self.lock:
            cur = self.conn.execute(
                """
                INSERT INTO scheduled_tasks (
                    description,
                    scheduled_for,
                    created_at,
                    status,
                    cron_expression,
                    timezone,
                    max_runs
                )
                VALUES (?, ?, ?, 'pending', ?, ?, ?)
                """,
                (description, scheduled_for.isoformat(), now, cron_expression, timezone, max_runs),
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
                SELECT id, description, cron_expression, timezone, run_count, max_runs, scheduled_for
                FROM scheduled_tasks
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
                cron_expression = row["cron_expression"]
                release_description = row["description"]
                if cron_expression:
                    self.conn.execute(
                        """
                        INSERT INTO tasks (
                            description,
                            status,
                            created_at,
                            updated_at,
                            agent_model,
                            result,
                            attempts,
                            max_attempts,
                            available_at,
                            idempotency_key,
                            priority,
                            last_error
                        )
                        VALUES (?, 'pending', ?, ?, NULL, NULL, 0, 3, ?, NULL, 0, NULL)
                        """,
                        (release_description, now, now, now),
                    )
                    next_base = datetime.fromisoformat(row["scheduled_for"])
                    iterator = croniter(cron_expression, next_base)
                    next_time = iterator.get_next(datetime)
                    run_count = row["run_count"] + 1
                    max_runs = row["max_runs"]
                    if max_runs is not None and run_count >= max_runs:
                        self.conn.execute(
                            """
                            UPDATE scheduled_tasks
                            SET status = 'completed', run_count = ?, last_run = ?, scheduled_for = ?
                            WHERE id = ?
                            """,
                            (run_count, now, next_time.isoformat(), row["id"]),
                        )
                    else:
                        self.conn.execute(
                            """
                            UPDATE scheduled_tasks
                            SET run_count = ?, last_run = ?, scheduled_for = ?
                            WHERE id = ?
                            """,
                            (run_count, now, next_time.isoformat(), row["id"]),
                        )
                else:
                    self.conn.execute(
                        "UPDATE scheduled_tasks SET status = 'released' WHERE id = ?",
                        (row["id"],),
                    )
                    self.conn.execute(
                        """
                        INSERT INTO tasks (
                            description,
                            status,
                            created_at,
                            updated_at,
                            agent_model,
                            result,
                            attempts,
                            max_attempts,
                            available_at,
                            idempotency_key,
                            priority,
                            last_error
                        )
                        VALUES (?, 'pending', ?, ?, NULL, NULL, 0, 3, ?, NULL, 0, NULL)
                        """,
                        (release_description, now, now, now),
                    )
                    self.conn.execute(
                        "UPDATE scheduled_tasks SET last_run = ? WHERE id = ?",
                        (now, row["id"]),
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
            now_iso = datetime.utcnow().isoformat()
            total = self.conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            pending_ready = self.conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 'pending' AND available_at <= ?",
                (now_iso,),
            ).fetchone()[0]
            pending_delayed = self.conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 'pending' AND available_at > ?",
                (now_iso,),
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
            "pending": pending_ready,
            "delayed": pending_delayed,
            "running": running,
            "completed": completed,
            "failed": failed,
        }

    def pending_count(self) -> int:
        with self.lock:
            now_iso = datetime.utcnow().isoformat()
            return self.conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 'pending' AND available_at <= ?",
                (now_iso,),
            ).fetchone()[0]


def run_task_loop(concurrency: int, agent_model: Optional[str] = None, autoscale: Optional[bool] = None) -> None:
    constants.refresh_paths()
    store = TaskStore(constants.TASK_DB)
    config = load_config()
    agent_defaults = config.get("models", {}).get("agent", {})
    resolved_model = agent_model or agent_defaults.get("name", config["agent_model"])
    runtime = get_runtime_settings()
    autoscale_cfg = runtime.get("autoscale", {})
    autoscale_flag = autoscale if autoscale is not None else autoscale_cfg.get("enabled", True)
    if autoscale_flag:
        autoscale_state = AgentDispatcher._build_autoscale_state(runtime)
    else:
        autoscale_state = AutoscaleState(
            enabled=False,
            max_concurrency=runtime.get("max_concurrency", 500),
            scale_up_pending_per_worker=int(autoscale_cfg.get("scale_up_pending_per_worker", 2)),
            scale_down_idle_cycles=int(autoscale_cfg.get("scale_down_idle_cycles", 3)),
        )

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
    memory_context: List[str] = []
    try:
        with default_memory_store() as memory_store:
            candidates = memory_store.search(task.description, limit=3)
            memory_context = [record.content for record in candidates]
    except Exception as exc:  # pragma: no cover
        write_system_log(f"Memory retrieval error for task {task.id}: {exc}")

    prompt_manager = default_prompt_manager()
    prompt_render = prompt_manager.render(
        task.description,
        context=memory_context,
        verification_steps=[
            "Confirm logical constraints for task outcome.",
            "Perform empirical validation (tests or command execution).",
        ],
    )
    write_agent_log(worker_id, "System prompt prepared:")
    for line in prompt_render.system_prompt.splitlines():
        write_agent_log(worker_id, f"  {line}")

    write_agent_log(worker_id, f"Task {task.id}: Execution started")
    # Simulate work
    time.sleep(0.5)
    # Logical verification
    logical_ok = bool(task.description.strip())
    write_agent_log(worker_id, f"Task {task.id}: Logical verification {'PASSED' if logical_ok else 'FAILED'}")
    if not logical_ok:
        store.fail_task(task, "Logical verification failed: empty description")
        write_agent_log(
            worker_id,
            f"Task {task.id}: Logical verification failed (attempt {task.attempts}/{task.max_attempts})",
        )
        return
    # Empirical verification (simulated)
    time.sleep(0.2)
    empirical_ok = True
    write_agent_log(worker_id, f"Task {task.id}: Empirical verification {'PASSED' if empirical_ok else 'FAILED'}")

    if empirical_ok:
        result_message = f"Completed with {agent_model}"
        store.complete_task(task.id, result_message)
        write_agent_log(worker_id, f"Task {task.id}: PASSED ✔ ({result_message})")
        try:
            with default_memory_store() as memory_store:
                memory_store.add_memory(
                    agent_id=f"agent-{worker_id:03d}",
                    content=f"Task {task.id}: {task.description} -> {result_message}",
                    metadata={
                        "task_id": task.id,
                        "agent_model": agent_model,
                        "attempts": task.attempts,
                    },
                )
        except Exception as exc:  # pragma: no cover - best effort
            write_system_log(f"Memory store error for task {task.id}: {exc}")
    else:  # pragma: no cover
        store.fail_task(task, "Empirical verification failed")
        write_agent_log(
            worker_id,
            f"Task {task.id}: FAILED during empirical verification (attempt {task.attempts}/{task.max_attempts})",
        )
