from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Sequence
from ..llm.client import LLMClient, extract_json
from ..policies.base import PrefixPolicy
from ..policies.llm_developer import LLMPolicyDeveloper

@dataclass(frozen=True)
class PolicyEvolutionEvent:
    cycle: int
    old_policy: str
    new_policy: str
    accepted: bool
    delta: float
    reason: str

class FailureDrivenPolicyEvolution:
    """Turns fresh/replay failures into explicit policy-development feedback."""
    def __init__(self, developer: LLMPolicyDeveloper): self.developer = developer
    def evolve(self, current: PrefixPolicy, observations: Sequence[dict[str, Any]], cycle: int) -> tuple[PrefixPolicy, PolicyEvolutionEvent]:
        candidate = self.developer.propose(current, list(observations))
        old_score = float(observations[-1].get("current_fresh", observations[-1].get("score", 0.0))) if observations else 0.0
        new_score = float(observations[-1].get("candidate_fresh", old_score)) if observations else old_score
        accepted = new_score >= old_score
        event = PolicyEvolutionEvent(cycle, current.name, candidate.name, accepted, new_score-old_score,
                                      "fresh_gate" if accepted else "candidate_below_fresh_baseline")
        return (candidate if accepted else current), event
