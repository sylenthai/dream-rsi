from __future__ import annotations
import json, logging, time
from dataclasses import asdict, dataclass

@dataclass(frozen=True)
class ExecutionAudit:
    run_id: str
    backend: str
    policy: dict
    returncode: int | None
    timed_out: bool
    duration_s: float
    output_truncated: bool = False

class ExecutionAuditLogger:
    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger("dream_rsi.execution")

    def emit(self, event: ExecutionAudit) -> None:
        payload = {"event":"execution.completed", "ts":time.time(), **asdict(event)}
        self.logger.info(json.dumps(payload, sort_keys=True))
