"""Agent worker pool and dispatcher."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Dict, Optional, Any

from ..config import get_runtime_settings
from ..logger import write_agent_log, write_system_log

if TYPE_CHECKING:  # pragma: no cover - typing support only
    from ..queue import Task, TaskStore
else:  # pragma: no cover - runtime only needs duck typing
    Task = Any  # type: ignore
    TaskStore = Any  # type: ignore


@dataclass
class AutoscaleState:
    enabled: bool
    max_concurrency: int
    scale_up_pending_per_worker: int
    scale_down_idle_cycles: int


class AgentDispatcher:
    """Coordinate worker threads that execute queued tasks."""

    def __init__(
        self,
        store: TaskStore,
        agent_model: str,
        process: Callable[[int, TaskStore, Task, str], None],
        initial_concurrency: Optional[int] = None,
        autoscale: Optional[AutoscaleState] = None,
    ) -> None:
        settings = get_runtime_settings()
        self.store = store
        self.agent_model = agent_model
        self.process = process
        self.runtime_settings = settings
        default = initial_concurrency or settings.get("default_concurrency", 10)
        max_concurrency = settings.get("max_concurrency", 500)
        self.target_concurrency = max(1, min(default, max_concurrency))
        self.autoscale = autoscale or self._build_autoscale_state(settings)
        self.max_concurrency = max_concurrency
        self.workers: Dict[int, threading.Thread] = {}
        self.worker_states: Dict[int, str] = {}
        self.stop_event = threading.Event()
        self._worker_id_seq = 0
        self._lock = threading.Lock()
        self._idle_cycles: Dict[int, int] = {}

    @staticmethod
    def _build_autoscale_state(settings: Dict) -> AutoscaleState:
        cfg = settings.get("autoscale", {})
        return AutoscaleState(
            enabled=bool(cfg.get("enabled", True)),
            max_concurrency=settings.get("max_concurrency", 500),
            scale_up_pending_per_worker=int(cfg.get("scale_up_pending_per_worker", 2)),
            scale_down_idle_cycles=int(cfg.get("scale_down_idle_cycles", 3)),
        )

    # ------------------------------------------------------------------
    def run(self) -> None:
        """Run until queue is drained and workers are idle."""

        manager_thread = threading.Thread(target=self._manage_pool, name="AgentDispatcherManager", daemon=True)
        manager_thread.start()
        try:
            while True:
                if self.stop_event.is_set():
                    break
                if self._all_tasks_completed():
                    # Ensure no pending work before exiting
                    if self.store.pending_count() == 0 and not self._has_running_workers():
                        break
                time.sleep(0.2)
        finally:
            self.stop_event.set()
            manager_thread.join()
            self._join_workers()
            write_system_log("Agent dispatcher run finished")

    # ------------------------------------------------------------------
    def _manage_pool(self) -> None:
        """Ensure the worker pool matches the desired concurrency and autoscale rules."""

        while not self.stop_event.is_set():
            self._ensure_workers()
            if self.autoscale.enabled:
                self._evaluate_autoscale()
            time.sleep(1.0)

    def _ensure_workers(self) -> None:
        with self._lock:
            current = len(self.workers)
            if current < self.target_concurrency:
                deficit = self.target_concurrency - current
                for _ in range(deficit):
                    self._spawn_worker()
            elif current > self.target_concurrency:
                excess = current - self.target_concurrency
                self._request_scale_down(excess)

    def _spawn_worker(self) -> None:
        self._worker_id_seq += 1
        worker_id = self._worker_id_seq

        thread = threading.Thread(target=self._worker_loop, args=(worker_id,), daemon=True)
        self.workers[worker_id] = thread
        self.worker_states[worker_id] = "starting"
        self._idle_cycles[worker_id] = 0
        thread.start()
        write_system_log(f"Agent worker {worker_id:03d} spawned (target {self.target_concurrency})")

    def _request_scale_down(self, excess: int) -> None:
        # Mark workers for shutdown by setting a high idle cycle threshold
        for worker_id in list(self.workers.keys()):
            if excess <= 0:
                break
            self._idle_cycles[worker_id] = max(self._idle_cycles[worker_id], self.autoscale.scale_down_idle_cycles + 1)
            excess -= 1

    def _evaluate_autoscale(self) -> None:
        pending = self.store.pending_count()
        active = len(self.workers)
        if pending <= 0 and active <= 1:
            return
        if active == 0:
            active = 1
        scale_up_threshold = active * self.autoscale.scale_up_pending_per_worker
        if pending > scale_up_threshold and self.target_concurrency < self.autoscale.max_concurrency:
            new_target = min(self.autoscale.max_concurrency, self.target_concurrency + max(1, pending // scale_up_threshold))
            if new_target != self.target_concurrency:
                self.target_concurrency = new_target
                write_system_log(f"Autoscale increased target workers to {self.target_concurrency}")
        elif pending < active and self.target_concurrency > 1:
            # scale down gradually
            self.target_concurrency = max(1, self.target_concurrency - 1)
            write_system_log(f"Autoscale decreased target workers to {self.target_concurrency}")

    def _worker_loop(self, worker_id: int) -> None:
        agent_model = self.agent_model
        idle_cycles = 0
        try:
            while not self.stop_event.is_set():
                task = self.store.claim_task()
                if not task:
                    idle_cycles += 1
                    self.worker_states[worker_id] = "idle"
                    if idle_cycles >= self.autoscale.scale_down_idle_cycles and worker_id in self.workers and len(self.workers) > self.target_concurrency:
                        break
                    time.sleep(0.5)
                    continue

                idle_cycles = 0
                self._idle_cycles[worker_id] = 0
                self.worker_states[worker_id] = f"running:{task.id}"
                write_agent_log(worker_id, f"Task {task.id} claimed by worker {worker_id:03d}")
                try:
                    self.process(worker_id, self.store, task, agent_model)
                except Exception as exc:  # pragma: no cover - handled by process
                    write_agent_log(worker_id, f"Execution error: {exc}")
                finally:
                    self.worker_states[worker_id] = "idle"

            write_agent_log(worker_id, "Worker shutting down")
        finally:
            with self._lock:
                self.workers.pop(worker_id, None)
                self.worker_states.pop(worker_id, None)
                self._idle_cycles.pop(worker_id, None)

    def _all_tasks_completed(self) -> bool:
        stats = self.store.stats()
        return stats["pending"] == 0 and stats["running"] == 0

    def _has_running_workers(self) -> bool:
        return any(state.startswith("running") for state in self.worker_states.values())

    def _join_workers(self) -> None:
        for worker in list(self.workers.values()):
            worker.join(timeout=1)
        self.workers.clear()
        self.worker_states.clear()


__all__ = ["AgentDispatcher", "AutoscaleState"]
