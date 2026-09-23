from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from .orchestrator import ResearchCycleResult

@dataclass(frozen=True)
class ResearchDecision:
    action: str
    reason: str
    evidence: dict[str, Any]

class ResearchDecisionEngine:
    """Conservative next-step policy; it never invents evidence."""
    def decide(self, result: ResearchCycleResult) -> ResearchDecision:
        if result.experiments == 0:
            return ResearchDecision("stop", "empty experiment plan", {})
        success_rate = result.succeeded / result.experiments
        if result.failed and success_rate < 0.5:
            return ResearchDecision("repair_or_replan", "too many experiment failures", {"success_rate": success_rate})
        if not result.aggregates:
            return ResearchDecision("collect_more_evidence", "requested metrics were not returned", {"success_rate": success_rate})
        return ResearchDecision("propose_next_hypothesis", "experiment completed with usable metric evidence", {"success_rate": success_rate, "aggregates": [a.__dict__ for a in result.aggregates]})
