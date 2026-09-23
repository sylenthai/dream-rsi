from __future__ import annotations
from dataclasses import dataclass
from .tree import DiscoveryTree, TreeView, Node
from .objective import ReplayMetrics, replay_score


@dataclass
class ReplayResult:
    world_id: str
    metrics: ReplayMetrics
    revealed: list[str]
    rounds: int


class ReplayWorld:
    """Replays a recorded discovery tree without executing generation/evaluation."""
    def __init__(self, world_id: str, tree: DiscoveryTree) -> None:
        self.world_id = world_id
        self.tree = tree

    def run(self, policy, max_parallelism: int, max_rounds: int,
            beta1: float = 0.01, beta2: float = 0.02) -> ReplayResult:
        policy.reset()
        revealed: set[str] = {"root"}
        observed_nodes = [self.tree.nodes["root"]]
        rounds = 0

        while rounds < max_rounds:
            view = TreeView(self.tree, revealed)
            batch = list(policy.select_batch(view, max_parallelism))
            legal = set(view.eligible())
            batch = list(dict.fromkeys(batch))
            if not batch:
                break
            if len(batch) > max_parallelism or any(x not in legal for x in batch):
                raise ValueError(f"Illegal replay batch: {batch}; legal={sorted(legal)}")

            new_nodes: list[Node] = []
            for parent_id in batch:
                parent = self.tree.nodes[parent_id]
                hidden_children = [c for c in parent.children if c not in revealed]
                if not hidden_children:
                    continue
                # Paper: non-root leaf exposes its unique next child; root opens earliest child.
                child_id = min(hidden_children, key=lambda x: self.tree.nodes[x].created_order)
                revealed.add(child_id)
                new_nodes.append(self.tree.nodes[child_id])

            if not new_nodes:
                break
            observed_nodes.extend(new_nodes)
            rounds += 1

            if len(revealed) == len(self.tree.nodes):
                break

        metrics = replay_score(observed_nodes, rounds, beta1, beta2)
        return ReplayResult(self.world_id, metrics, sorted(revealed), rounds)
