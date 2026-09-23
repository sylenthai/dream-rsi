from __future__ import annotations
from dataclasses import dataclass
from .tree import Node


@dataclass(frozen=True)
class ReplayMetrics:
    quality: float
    work: int
    rounds: int
    parallelism_bonus: float
    reward: float


def replay_score(nodes: list[Node], rounds: int, beta1: float = 0.01,
                 beta2: float = 0.02) -> ReplayMetrics:
    non_root = [n for n in nodes if n.id != "root"]
    quality = max((n.score for n in non_root if n.score is not None), default=float("-inf"))
    work = len(non_root)
    bonus = work / max(1, rounds)
    reward = quality - beta1 * work + beta2 * bonus
    return ReplayMetrics(quality, work, rounds, bonus, reward)
