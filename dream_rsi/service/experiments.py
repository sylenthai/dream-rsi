from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4
from typing import Any
from .queue import Job, JobQueue

@dataclass
class ExperimentRecord:
    id: str
    task: str
    config: dict[str, Any]
    status: str = "queued"
    attempts: int = 0
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ExperimentService:
    """Persistent orchestration boundary: create a run and enqueue work; workers execute it."""
    def __init__(self, store=None, queue: JobQueue | None = None):
        self.store, self.queue = store, queue or JobQueueFallback()
        self._records: dict[str, ExperimentRecord] = {}; self._lock = Lock()

    def submit(self, task: str, config: dict[str, Any], idempotency_key: str | None = None) -> ExperimentRecord:
        if idempotency_key:
            if self.store and hasattr(self.store, "find_by_idempotency"):
                old=self.store.find_by_idempotency(idempotency_key)
                if old: return ExperimentRecord(old["id"], old["task"], old["config"], old["status"], old.get("attempts",0), old.get("result"), old.get("error"), str(old["created_at"]))
            with self._lock:
                for r in self._records.values():
                    if r.config.get("_idempotency_key") == idempotency_key: return r
        run_id = str(uuid4()); payload = dict(config)
        if idempotency_key: payload["_idempotency_key"] = idempotency_key
        record = ExperimentRecord(run_id, task, payload)
        with self._lock: self._records[run_id] = record
        if self.store: self.store.create_run(run_id, task, payload)
        self.queue.enqueue(Job(run_id, task, payload))
        return record

    def get(self, run_id: str) -> ExperimentRecord | None:
        if self.store:
            r = self.store.get_run(run_id)
            if r:
                return ExperimentRecord(r["id"], r["task"], r["config"], r["status"], r.get("attempts",0), r.get("result"), r.get("error"), str(r["created_at"]))
        with self._lock: return self._records.get(run_id)

class JobQueueFallback:
    def __init__(self): self._jobs = []
    def enqueue(self, job): self._jobs.append(job)
    def dequeue(self, timeout=1.0): return self._jobs.pop(0) if self._jobs else None
