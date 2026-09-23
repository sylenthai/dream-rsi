from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Any


@dataclass
class ToyDiscoveryAgent:
    """Deterministic stand-in for an expensive LLM discovery agent."""
    seed: int = 7

    def generate(self, parent_id: str, context: dict[str, Any]):
        tree = context["tree"]
        parent = tree.nodes[parent_id]
        # A synthetic landscape: some branches improve quickly, others plateau.
        attempt = len(parent.children) + parent.depth + self.seed
        score = 0.55 + 0.08 * parent.depth + 0.12 * math.sin(attempt * 1.7)
        score = round(score, 6)
        from dream_rsi.core.interfaces import CandidateResult
        return CandidateResult(score=score, success=True,
                               diagnostics={"synthetic": True, "parent": parent_id})
