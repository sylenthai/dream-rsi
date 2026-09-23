from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from concurrent.futures import ThreadPoolExecutor
from ..core.tree import DiscoveryTree

@dataclass(frozen=True)
class FreshValidationResult:
    policy_name: str
    score: float
    success: bool
    details: dict[str, Any]

class FreshValidator:
    """Independent fresh-state validation over repeated deterministic samples."""
    def __init__(self, agent, evaluator=None, workers: int = 4, rounds: int = 5, samples: int = 3):
        self.agent = agent
        self.evaluator = evaluator
        self.workers = max(1, workers)
        self.rounds = max(1, rounds)
        self.samples = max(1, samples)

    def _rollout(self, policy):
        tree = DiscoveryTree(); policy.reset()
        for _ in range(self.rounds):
            view = tree.clone_view()
            batch = list(dict.fromkeys(policy.select_batch(view, self.workers)))
            legal = set(view.eligible())
            if len(batch) > self.workers or any(x not in legal for x in batch):
                raise ValueError(f"illegal policy batch: {batch}")
            if not batch: break
            def one(parent_id):
                result = self.agent.generate(parent_id, {"tree": tree, "parent_id": parent_id, "fresh": True})
                return self.evaluator.evaluate(result) if self.evaluator else result
            with ThreadPoolExecutor(max_workers=min(self.workers, len(batch))) as pool:
                futures = [pool.submit(one, p) for p in batch]
                results = [f.result() for f in futures]
            for parent_id, result in zip(batch, results):
                tree.add_child(parent_id, result.score, result.success, dict(result.diagnostics or {}))
        return tree

    def validate(self, policy, rounds: int | None = None):
        old_rounds = self.rounds
        if rounds is not None: self.rounds = max(1, rounds)
        try:
            scores = [self._rollout(policy).best_score() for _ in range(self.samples)]
        finally:
            self.rounds = old_rounds
        score = sum(scores) / len(scores) if scores else float("-inf")
        return FreshValidationResult(policy.name, score, bool(scores), {
            "samples": len(scores), "rounds": self.rounds, "independent": True,
            "sample_scores": scores,
        })
