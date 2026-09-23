from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
import math
import statistics
import time
from typing import Any, Callable

from .researcher import ExperimentPlan, Hypothesis
from .memory import ResearchMemoryStore

@dataclass(frozen=True)
class ExperimentAggregate:
    metric: str
    count: int
    mean: float
    median: float
    stddev: float
    min_value: float
    max_value: float

@dataclass(frozen=True)
class ResearchCycleResult:
    hypothesis_id: str
    experiments: int
    succeeded: int
    failed: int
    started_at: float
    elapsed_seconds: float
    results: tuple[dict[str, Any], ...]
    aggregates: tuple[ExperimentAggregate, ...] = ()

class ResearchOrchestrator:
    """Runs a validated experiment plan with bounded parallelism and result aggregation."""
    def __init__(self, runner: Callable[[str, str, int], dict[str, Any]], memory: ResearchMemoryStore | None = None, max_workers: int = 4):
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        self.runner = runner
        self.memory = memory
        self.max_workers = max_workers

    def _cases(self, plan: ExperimentPlan):
        for task in plan.tasks:
            for method in plan.methods:
                for seed in plan.seeds:
                    for repetition in range(plan.repetitions):
                        yield task, method, seed, repetition

    def _run_case(self, case):
        task, method, seed, repetition = case
        try:
            result = dict(self.runner(task, method, seed))
            result.update(task_id=task, method=method, seed=seed, repetition=repetition, status="succeeded")
        except Exception as exc:
            result = {"task_id": task, "method": method, "seed": seed, "repetition": repetition, "status": "failed", "error": str(exc)}
        return result

    @staticmethod
    def _aggregate(results: list[dict[str, Any]], metrics: tuple[str, ...]) -> tuple[ExperimentAggregate, ...]:
        out = []
        for metric in metrics:
            values = []
            for r in results:
                if r.get("status") != "succeeded":
                    continue
                try:
                    value = float(r[metric])
                    if math.isfinite(value): values.append(value)
                except (KeyError, TypeError, ValueError):
                    continue
            if values:
                out.append(ExperimentAggregate(metric, len(values), statistics.fmean(values), statistics.median(values), statistics.stdev(values) if len(values) > 1 else 0.0, min(values), max(values)))
        return tuple(out)

    def run(self, hypothesis: Hypothesis, plan: ExperimentPlan) -> ResearchCycleResult:
        start = time.time()
        cases = list(self._cases(plan))
        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, max(1, len(cases)))) as pool:
            futures = [pool.submit(self._run_case, case) for case in cases]
            for future in as_completed(futures):
                results.append(future.result())
        results.sort(key=lambda r: (r["task_id"], r["method"], int(r["seed"]), int(r["repetition"])))
        aggregates = self._aggregate(results, hypothesis.metrics)
        out = ResearchCycleResult(hypothesis.id, len(results), sum(r["status"] == "succeeded" for r in results), sum(r["status"] == "failed" for r in results), start, time.time()-start, tuple(results), aggregates)
        if self.memory:
            self.memory.put("research_result", asdict(out))
        return out
