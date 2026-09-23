from __future__ import annotations

import os
import threading
import time
from typing import Any, Callable

from .queue import Job, JobQueue
from ..observability import METRICS, span
from ..observability.events import EventLog

Handler = Callable[[str, dict[str, Any]], dict[str, Any]]


class ExperimentWorker:
    """Worker process executing queued experiment jobs with heartbeats and retries."""

    def __init__(
        self,
        store: Any,
        queue: JobQueue,
        handlers: dict[str, Handler],
        max_attempts: int = 3,
        poll_timeout: float = 1.0,
        heartbeat_interval: float = 5.0,
        worker_id: str | None = None,
        reclaim_interval: float = 10.0,
    ):
        self.store = store
        self.queue = queue
        self.handlers = handlers
        self.max_attempts = max_attempts
        self.poll_timeout = poll_timeout
        self.events = EventLog("dream_rsi.worker")
        self.running = True
        self.worker_id = worker_id or os.getenv("HOSTNAME") or f"worker-{os.getpid()}"
        self.heartbeat_interval = heartbeat_interval
        self.reclaim_interval = reclaim_interval
        self._last_beat = 0.0
        self._last_reclaim = 0.0
        self._cancel: set[str] = set()
        self._lock = threading.Lock()

    def heartbeat(self) -> None:
        now = time.time()
        if now - self._last_beat >= self.heartbeat_interval:
            fn = getattr(self.store, "heartbeat_worker", None)
            if fn:
                fn(self.worker_id, now)
            self._last_beat = now
            METRICS.inc("dream_rsi_worker_heartbeats_total")

    def cancel(self, run_id: str) -> None:
        with self._lock:
            self._cancel.add(run_id)

    def _is_cancelled(self, run_id: str) -> bool:
        with self._lock:
            if run_id in self._cancel:
                return True
        if self.store and hasattr(self.store, "get_run"):
            run = self.store.get_run(run_id)
            if run and run.get("status") == "cancelled":
                return True
        return False

    def reclaim(self) -> int:
        now = time.time()
        if now - self._last_reclaim < self.reclaim_interval:
            return 0
        fn = getattr(self.queue, "reclaim_stale", None)
        jobs = fn() if fn else []
        self._last_reclaim = now
        for job in jobs:
            if getattr(self.store, "get_run", lambda _: None)(job.run_id):
                self._process(job, reclaimed=True)
        return len(jobs)

    def process_once(self) -> bool:
        self.heartbeat()
        self.reclaim()
        job = self.queue.dequeue(self.poll_timeout)
        if job is None:
            return False
        self._process(job)
        return True

    def _process(self, job: Job, reclaimed: bool = False) -> None:
        if self._is_cancelled(job.run_id):
            self.store.update_run(job.run_id, "cancelled", attempts=job.attempt)
            getattr(self.queue, "ack", lambda _: None)(job)
            return

        attempt = job.attempt + 1
        self.store.update_run(job.run_id, "running", attempts=attempt)
        start = time.perf_counter()
        METRICS.inc("dream_rsi_jobs_total", task=job.task, status="started")
        self.events.emit(
            "job_started",
            run_id=job.run_id,
            task=job.task,
            attempt=attempt,
            worker_id=self.worker_id,
            reclaimed=reclaimed,
        )

        try:
            handler = self.handlers[job.task]
            with span("dream_rsi.job", run_id=job.run_id, task=job.task, attempt=attempt):
                result = handler(job.task, job.config)

            if self._is_cancelled(job.run_id):
                self.store.update_run(job.run_id, "cancelled", attempts=attempt)
            else:
                self.store.update_run(job.run_id, "succeeded", attempts=attempt, result=result)

            getattr(self.queue, "ack", lambda _: None)(job)
            METRICS.inc("dream_rsi_jobs_total", task=job.task, status="succeeded")
            METRICS.observe("dream_rsi_job_duration_seconds", time.perf_counter() - start, task=job.task)

        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            if attempt < self.max_attempts:
                self.store.update_run(job.run_id, "retrying", attempts=attempt, error=message)
                self.queue.enqueue(Job(job.run_id, job.task, job.config, attempt))
                getattr(self.queue, "ack", lambda _: None)(job)
                METRICS.inc("dream_rsi_job_retries_total", task=job.task)
            else:
                self.store.update_run(job.run_id, "failed", attempts=attempt, error=message)
                getattr(self.queue, "dead_letter", lambda *_: None)(job, message)
                getattr(self.queue, "ack", lambda _: None)(job)
                METRICS.inc("dream_rsi_jobs_total", task=job.task, status="dead_letter")

    def run_forever(self) -> None:
        while self.running:
            self.process_once()

    def stop(self) -> None:
        self.running = False
