from __future__ import annotations
from .heuristic import ConservativePolicy


class WidthPolicy(ConservativePolicy):
    name = "width"
    def __init__(self, beta: float = 0.7):
        super().__init__(beta)


class PolicyMutator:
    """Placeholder for the paper's fixed LLM policy-development agent.

    The interface is intentionally tiny so an API-backed code-rewriter can replace this later.
    """
    def propose(self, current, feedback):
        if getattr(current, "beta", 0.35) < 0.6:
            return WidthPolicy(0.7)
        return ConservativePolicy(0.25)
