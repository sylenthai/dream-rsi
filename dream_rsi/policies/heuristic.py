from __future__ import annotations
from .base import PrefixPolicy


class ConservativePolicy(PrefixPolicy):
    name = "conservative"
    def __init__(self, beta: float = 0.35):
        self.beta = beta

    def select_batch(self, view, max_parallelism):
        eligible = view.eligible()
        if not eligible:
            return []
        # Root opens new branches. For existing leaves, prioritize relative improvement.
        leaves = [x for x in eligible if x != "root"]
        ranked = sorted(leaves, key=lambda x: self._priority(view, x), reverse=True)
        # Root is the exploration action: keep opening new branches when the
        # policy is sufficiently exploratory, while retaining exploitation slots.
        if self.beta >= 0.6:
            portfolio = ["root"] + ranked
            return portfolio[:min(max_parallelism, len(portfolio))]
        if ranked:
            return ranked[:1]
        return ["root"]

    def _priority(self, view, node_id):
        node = view.node(node_id)
        if node.score is None:
            return 0.0
        parent_score = -float("inf")
        if node.parent_id and node.parent_id != "root":
            parent = view.node(node.parent_id)
            if parent.score is not None:
                parent_score = parent.score
        gain = node.score - parent_score if parent_score != -float("inf") else node.score
        return gain + 0.001 * node.depth
