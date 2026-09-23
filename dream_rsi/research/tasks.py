from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable

from ..core.interfaces import CandidateResult


@dataclass(frozen=True)
class DiscoveryTask:
    task_id: str
    split: str
    seed_offset: int
    phase: float
    depth_gain: float
    optimal_branch: int = 0
    branch_bonus: float = 0.0
    noise: float = 0.0


class TaskAwareToyAgent:
    """Task-conditioned synthetic agent used to test train/held-out generalization.

    This is deliberately not presented as a real LLM benchmark. It provides a
    reproducible task adapter with distribution shift between train and test.
    """

    def __init__(self, task: DiscoveryTask, seed: int = 0):
        self.task = task
        self.seed = seed

    def generate(self, parent_id: str, context: dict[str, Any]) -> CandidateResult:
        tree = context["tree"]
        parent = tree.nodes[parent_id]
        attempt = len(parent.children) + parent.depth + self.seed + self.task.seed_offset
        signal = math.sin(attempt * 1.37 + self.task.phase)
        branch_bonus = 0.0
        if parent_id == "root":
            branch_index = len(parent.children)
            if branch_index == self.task.optimal_branch:
                branch_bonus = self.task.branch_bonus
        score = 0.50 + self.task.depth_gain * parent.depth + 0.16 * signal + branch_bonus
        if self.task.noise:
            # deterministic pseudo-noise, preserving reproducibility
            score += self.task.noise * math.sin(attempt * 2.11 + self.seed)
        score = max(0.0, min(1.0, round(score, 6)))
        return CandidateResult(
            score=score,
            success=True,
            diagnostics={"task_id": self.task.task_id, "split": self.task.split},
        )


@dataclass(frozen=True)
class TaskSuite:
    train: tuple[DiscoveryTask, ...]
    validation: tuple[DiscoveryTask, ...]
    test: tuple[DiscoveryTask, ...]

    @property
    def held_out(self) -> tuple[DiscoveryTask, ...]:
        return self.validation + self.test


def default_task_suite() -> TaskSuite:
    # Train/test differ in phase and depth-gain ranges. This creates a modest
    # distribution shift without pretending to model a real-world domain.
    train = tuple(
        DiscoveryTask(f"train-{i}", "train", 1000 + i, phase=0.15 * i,
                      depth_gain=0.055 + 0.004 * (i % 3), optimal_branch=i % 2,
                      branch_bonus=0.08, noise=0.015)
        for i in range(6)
    )
    validation = tuple(
        DiscoveryTask(f"val-{i}", "validation", 2000 + i, phase=0.9 + 0.2 * i,
                      depth_gain=0.050 + 0.003 * (i % 2), optimal_branch=1,
                      branch_bonus=0.10, noise=0.02)
        for i in range(3)
    )
    test = tuple(
        DiscoveryTask(f"test-{i}", "test", 3000 + i, phase=2.0 + 0.25 * i,
                      depth_gain=0.020 + 0.002 * (i % 3), optimal_branch=2,
                      branch_bonus=0.25, noise=0.025)
        for i in range(4)
    )
    return TaskSuite(train=train, validation=validation, test=test)


def get_split(suite: TaskSuite, split: str) -> tuple[DiscoveryTask, ...]:
    if split == "train":
        return suite.train
    if split == "validation":
        return suite.validation
    if split == "test":
        return suite.test
    if split == "held-out":
        return suite.held_out
    raise ValueError(f"unknown split: {split}")
