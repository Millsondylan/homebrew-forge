"""Load testing utilities for AgentForge."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Optional

from . import constants
from .config import get_runtime_settings
from .logger import write_system_log
from .queue import TaskStore, run_task_loop


def run_load_test(agents: int, tasks: int, report_path: Path, reset: bool = False) -> dict:
    constants.refresh_paths()
    if reset and constants.TASK_DB.exists():
        constants.TASK_DB.unlink()

    store = TaskStore(constants.TASK_DB)
    try:
        existing = store.stats()["pending"] + store.stats()["running"]
        remaining = max(0, tasks - existing)
        for idx in range(remaining):
            store.add_task(f"loadtest task {idx}")
    finally:
        store.close()

    runtime = get_runtime_settings()
    concurrency = min(agents, runtime.get("max_concurrency", agents))
    start = time.perf_counter()
    run_task_loop(concurrency=concurrency, autoscale=True)
    duration = time.perf_counter() - start

    store = TaskStore(constants.TASK_DB)
    try:
        stats = store.stats()
    finally:
        store.close()

    report = {
        "agents_requested": agents,
        "concurrency_used": concurrency,
        "tasks": tasks,
        "duration_seconds": duration,
        "queue_stats": stats,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_system_log(
        f"Load test completed: agents={agents}, tasks={tasks}, duration={duration:.2f}s",
        extra={"report": str(report_path)},
    )
    return report


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Run AgentForge load test")
    parser.add_argument("--agents", type=int, default=100, help="Number of concurrent agents to simulate")
    parser.add_argument("--tasks", type=int, default=200, help="Number of tasks to enqueue for the load test")
    parser.add_argument("--report", type=Path, default=Path("reports/loadtest.json"), help="Path to write load test report")
    parser.add_argument("--reset", action="store_true", help="Reset the task database before load test")
    args = parser.parse_args(argv)

    run_load_test(args.agents, args.tasks, args.report, reset=args.reset)


if __name__ == "__main__":
    main()
