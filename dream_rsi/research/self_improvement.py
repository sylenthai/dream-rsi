from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

from .decision import ResearchDecision
from .memory import ResearchMemoryStore
from .researcher import Hypothesis, ResearchMutation, LLMResearcher
from .orchestrator import ResearchCycleResult

@dataclass(frozen=True)
class FailureDiagnosis:
    category: str
    summary: str
    evidence: tuple[dict[str, Any], ...]
    confidence: float

@dataclass(frozen=True)
class ImprovementStep:
    hypothesis_id: str
    diagnosis: FailureDiagnosis | None
    mutation: ResearchMutation | None
    action: str
    rationale: str

class FailureAnalyzer:
    """Deterministic first-pass diagnosis; no unsupported causal claims."""
    def diagnose(self, result: ResearchCycleResult) -> FailureDiagnosis | None:
        failures = [r for r in result.results if r.get("status") == "failed"]
        if not failures:
            return None
        timeouts = [r for r in failures if "timeout" in str(r.get("error", "")).lower()]
        if len(timeouts) == len(failures):
            category = "timeout"
        elif len(failures) / max(1, result.experiments) >= 0.5:
            category = "high_failure_rate"
        else:
            category = "mixed_failure"
        evidence = tuple({"task_id": r.get("task_id"), "method": r.get("method"), "seed": r.get("seed"), "error": r.get("error", "")} for r in failures[:20])
        confidence = min(1.0, len(failures) / max(1, result.experiments))
        return FailureDiagnosis(category, f"Observed {len(failures)} failed experiment(s); category={category}", evidence, confidence)

class SelfImprovementEngine:
    """Turns observed failures/evidence into bounded strategy mutations."""
    def __init__(self, researcher: LLMResearcher, memory: ResearchMemoryStore | None = None):
        self.researcher = researcher
        self.memory = memory
        self.analyzer = FailureAnalyzer()

    def improve(self, hypothesis: Hypothesis, result: ResearchCycleResult, decision: ResearchDecision, allowed_changes: list[str] | None = None) -> ImprovementStep:
        diagnosis = self.analyzer.diagnose(result)
        if decision.action == "repair_or_replan" and diagnosis:
            mutation = self.researcher.mutate(hypothesis, asdict(diagnosis), allowed_changes)
            step = ImprovementStep(hypothesis.id, diagnosis, mutation, "mutate_strategy", mutation.change)
        elif decision.action == "collect_more_evidence":
            step = ImprovementStep(hypothesis.id, diagnosis, None, "collect_more_evidence", "Run additional evidence-gathering experiments before changing strategy.")
        elif decision.action == "propose_next_hypothesis":
            step = ImprovementStep(hypothesis.id, diagnosis, None, "propose_next_hypothesis", "Current evidence is usable; generate a new falsifiable hypothesis without claiming causality.")
        else:
            step = ImprovementStep(hypothesis.id, diagnosis, None, "stop", decision.reason)
        if self.memory:
            self.memory.put("improvement_step", asdict(step))
        return step
