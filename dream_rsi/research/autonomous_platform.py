from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from .decision import ResearchDecisionEngine
from .memory import ResearchMemoryStore
from .orchestrator import ResearchOrchestrator, ResearchCycleResult
from .researcher import ExperimentPlan, Hypothesis, LLMResearcher
from .self_improvement import ImprovementStep, SelfImprovementEngine


@dataclass(frozen=True)
class AutonomousResearchConfig:
    max_cycles: int = 3
    max_experiments: int = 100
    max_consecutive_failures: int = 2
    max_workers: int = 4
    benchmark_split: str = "test"
    available_tasks: tuple[str, ...] = ()
    methods: tuple[str, ...] = ()
    seeds: tuple[int, ...] = (0,)
    allowed_changes: tuple[str, ...] = ()
    checkpoint_path: str | None = None


@dataclass(frozen=True)
class AutonomousCycle:
    cycle: int
    hypothesis: Hypothesis
    plan: ExperimentPlan
    result: ResearchCycleResult
    decision_action: str
    decision_reason: str
    improvement: ImprovementStep


@dataclass(frozen=True)
class AutonomousResearchRun:
    run_id: str
    status: str
    started_at: float
    elapsed_seconds: float
    cycles: tuple[AutonomousCycle, ...]
    stop_reason: str


class AutonomousResearchController:
    """Bounded controller joining researcher, orchestrator, decision and memory.

    Safety properties:
    - bounded cycles and experiment count;
    - validated task/method/seed choices delegated to LLMResearcher.plan;
    - no direct code execution by the controller;
    - checkpoint after every completed cycle;
    - explicit stop conditions instead of open-ended recursion.
    """

    def __init__(
        self,
        researcher: LLMResearcher,
        runner: Callable[[str, str, int], dict[str, Any]],
        memory: ResearchMemoryStore | None = None,
        config: AutonomousResearchConfig | None = None,
        run_id: str | None = None,
    ):
        self.researcher = researcher
        self.memory = memory
        self.config = config or AutonomousResearchConfig()
        self.run_id = run_id or f"rsi-{int(time.time() * 1000)}"
        self.orchestrator = ResearchOrchestrator(
            runner, memory=memory, max_workers=self.config.max_workers
        )
        self.decision_engine = ResearchDecisionEngine()
        self.improvement_engine = SelfImprovementEngine(researcher, memory=memory)

    def _checkpoint(self, state: dict[str, Any]) -> None:
        path = self.config.checkpoint_path
        if not path:
            return
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True, default=str), encoding="utf-8")
        tmp.replace(target)

    def run(self, context: dict[str, Any]) -> AutonomousResearchRun:
        cfg = self.config
        if cfg.max_cycles < 1 or cfg.max_experiments < 1:
            raise ValueError("max_cycles and max_experiments must be >= 1")
        if not cfg.available_tasks or not cfg.methods or not cfg.seeds:
            raise ValueError("available_tasks, methods and seeds must be non-empty")

        started = time.time()
        cycles: list[AutonomousCycle] = []
        total_experiments = 0
        consecutive_failures = 0
        current_context = dict(context)
        stop_reason = "cycle_budget_exhausted"

        for cycle_no in range(1, cfg.max_cycles + 1):
            hypothesis = self.researcher.propose(current_context)
            plan = self.researcher.plan(
                hypothesis,
                list(cfg.available_tasks),
                list(cfg.methods),
                list(cfg.seeds),
                split=cfg.benchmark_split,
            )
            planned_cases = len(plan.tasks) * len(plan.methods) * len(plan.seeds) * plan.repetitions
            if planned_cases == 0:
                stop_reason = "empty_plan"
                break
            if total_experiments + planned_cases > cfg.max_experiments:
                stop_reason = "experiment_budget_exhausted"
                break

            result = self.orchestrator.run(hypothesis, plan)
            total_experiments += result.experiments
            consecutive_failures = consecutive_failures + 1 if result.failed else 0
            decision = self.decision_engine.decide(result)
            improvement = self.improvement_engine.improve(
                hypothesis,
                result,
                decision,
                list(cfg.allowed_changes),
            )
            cycle = AutonomousCycle(
                cycle_no, hypothesis, plan, result, decision.action, decision.reason, improvement
            )
            cycles.append(cycle)
            self._checkpoint({
                "run_id": self.run_id,
                "status": "running",
                "cycle": cycle_no,
                "total_experiments": total_experiments,
                "consecutive_failures": consecutive_failures,
                "cycle_result": asdict(cycle),
            })

            if consecutive_failures >= cfg.max_consecutive_failures:
                stop_reason = "consecutive_failure_guard"
                break
            if decision.action == "stop":
                stop_reason = decision.reason
                break

            current_context = {
                **current_context,
                "previous_hypothesis": asdict(hypothesis),
                "previous_result": asdict(result),
                "previous_decision": asdict(decision),
                "improvement_step": asdict(improvement),
            }

        status = "succeeded" if cycles and stop_reason in {
            "cycle_budget_exhausted", "experiment_budget_exhausted", "experiment completed with usable metric evidence"
        } else "stopped"
        run = AutonomousResearchRun(
            self.run_id, status, started, time.time() - started, tuple(cycles), stop_reason
        )
        self._checkpoint({"run_id": self.run_id, "status": status, "run": asdict(run)})
        if self.memory:
            self.memory.put("autonomous_run", asdict(run))
        return run
