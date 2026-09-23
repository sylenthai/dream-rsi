from __future__ import annotations
from dataclasses import dataclass, asdict
import json, time
from pathlib import Path
from typing import Any
from ..evaluators.coding import CodingTestEvaluator
from ..execution.secure import SecurePythonExecutor
from ..llm.client import LLMClient
from .full_rsi import run_full_rsi
from .task_registry import CodingBenchmarkTask

@dataclass(frozen=True)
class RealExperimentReport:
    model: str
    tasks: list[dict[str, Any]]
    started_at_epoch: float
    elapsed_s: float


def run_real_experiment(llm: LLMClient, tasks: tuple[CodingBenchmarkTask, ...], **kwargs) -> RealExperimentReport:
    start = time.time(); wall = time.perf_counter(); rows=[]
    for task in tasks:
        executor = SecurePythonExecutor(prefer_docker=True, allow_local_fallback=False)
        result = run_full_rsi(llm, task.task, task.tests, executor=executor, **kwargs)
        row = asdict(result)
        row["benchmark"] = task.manifest()
        row["executor"] = "docker-first"
        row["docker_available"] = getattr(executor.docker, "available", False)
        row["executor_mode"] = executor.mode
        rows.append(row)
    return RealExperimentReport(llm.model, rows, start, time.perf_counter()-wall)


def save_real_experiment(path: str | Path, report: RealExperimentReport) -> None:
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False), encoding="utf-8")
