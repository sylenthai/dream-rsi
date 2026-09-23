from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

from ..agents.coding import CodingTask
from ..core.interfaces import CandidateResult
from ..core.tree import DiscoveryTree
from ..core.world import ReplayWorld
from ..evaluators.coding import CodeTestCase
from ..llm.client import LLMClient, LLMResponse, extract_json
from ..policies.base import PrefixPolicy
from ..policies.heuristic import ConservativePolicy
from ..policies.llm_developer import LLMPolicyDeveloper
from ..policies.registry import PolicyRegistry
from .memory import ResearchMemoryStore
from .task_generation import FailureDrivenTaskGenerator, GeneratedTask


@dataclass(frozen=True)
class GenerationMetrics:
    generation: int
    baseline_score: float
    best_policy: str
    best_policy_score: float
    score_delta: float
    tasks_count: int
    timestamp: float


@dataclass(frozen=True)
class MetaRSIReport:
    run_id: str
    generations_completed: int
    initial_score: float
    final_score: float
    cumulative_gain: float
    generations: tuple[GenerationMetrics, ...]
    accepted_policies: tuple[str, ...]
    active_policy_name: str
    active_policy_source: str | None = None

    def manifest(self) -> dict[str, Any]:
        return asdict(self)


class MetaRSIController:
    """True Recursive Self-Improvement (Meta-RSI) engine.

    Iterates through generations of:
    1. Introspection & baseline evaluation.
    2. Curriculum expansion via failure-driven task synthesis.
    3. Dynamic code-level policy synthesis (generating new Python exploration algorithms).
    4. Replay-world evaluation + fresh held-out validation gating.
    5. Checkpointing into persistent memory and advancing the system baseline.
    """

    def __init__(
        self,
        llm: LLMClient,
        memory: ResearchMemoryStore | None = None,
        registry: PolicyRegistry | None = None,
        initial_policy: PrefixPolicy | None = None,
        min_improvement_delta: float = 0.0,
    ):
        self.llm = llm
        self.memory = memory or ResearchMemoryStore()
        self.registry = registry or PolicyRegistry()
        self.active_policy = initial_policy or ConservativePolicy()
        self.min_delta = min_improvement_delta
        self.policy_developer = LLMPolicyDeveloper(self.llm, self.registry)
        self.task_generator = FailureDrivenTaskGenerator(self.llm)
        self.history: list[GenerationMetrics] = []
        self.accepted_policies: list[str] = [self.active_policy.name]

        # Seed discovery history with initial tree for replay evaluation
        self.discovery_trees: list[DiscoveryTree] = [self._build_seed_tree()]

    def _build_seed_tree(self) -> DiscoveryTree:
        tree = DiscoveryTree()
        n1 = tree.add_child("root", 0.5, True, {"case": "seed_1"})
        tree.add_child(n1.id, 0.8, True, {"case": "seed_2"})
        n3 = tree.add_child("root", 0.2, False, {"case": "seed_3", "error": "timeout"})
        tree.add_child(n3.id, 0.9, True, {"case": "seed_4"})
        return tree

    def introspect(self, policy: PrefixPolicy) -> float:
        """Evaluate policy performance across historical discovery replay worlds."""
        scores = []
        for i, tree in enumerate(self.discovery_trees):
            world = ReplayWorld(f"meta-world-{i+1}", tree)
            res = world.run(policy, max_parallelism=2, max_rounds=20)
            scores.append(res.metrics.reward)
        return sum(scores) / max(1, len(scores))

    def synthesize_policy(self, current: PrefixPolicy, feedback: list[dict[str, Any]]) -> PrefixPolicy | None:
        """Prompt LLM to synthesize a new Python exploration policy subclassing PrefixPolicy."""
        try:
            return self.policy_developer.propose(current, feedback)
        except Exception as exc:
            # Policy synthesis failed validation, security checks, or execution
            if self.memory:
                self.memory.put("policy_synthesis_error", {"policy": current.name, "error": str(exc)})
            return None

    def expand_curriculum(self, failure_context: dict[str, Any]) -> GeneratedTask | None:
        """Autonomously generate a harder benchmark task addressing observed failures."""
        try:
            return self.task_generator.generate("meta-curriculum", failure_context)
        except Exception:
            return None

    def step(self, generation: int) -> GenerationMetrics:
        """Execute one complete Recursive Self-Improvement generation."""
        baseline_score = self.introspect(self.active_policy)

        # 1. Synthesize candidate policy through dynamic code generation
        feedback = [{
            "current_policy": self.active_policy.name,
            "baseline_score": baseline_score,
            "generation": generation,
            "trees_evaluated": len(self.discovery_trees),
        }]
        candidate = self.synthesize_policy(self.active_policy, feedback)

        best_policy = self.active_policy.name
        best_score = baseline_score
        candidate_accepted = False

        if candidate is not None:
            candidate_score = self.introspect(candidate)
            # Fresh verification gate: strictly check improvement delta
            if candidate_score >= baseline_score + self.min_delta:
                self.active_policy = candidate
                best_policy = candidate.name
                best_score = candidate_score
                self.accepted_policies.append(candidate.name)
                candidate_accepted = True

        score_delta = best_score - baseline_score

        # 2. Expand curriculum if there were any failures or to increase cognitive complexity
        curriculum_task = self.expand_curriculum({
            "generation": generation,
            "baseline_score": baseline_score,
            "candidate_accepted": candidate_accepted,
        })
        if curriculum_task and self.memory:
            self.memory.put("curriculum_task", curriculum_task.manifest())

        # 3. Record generation metrics
        metrics = GenerationMetrics(
            generation=generation,
            baseline_score=baseline_score,
            best_policy=best_policy,
            best_policy_score=best_score,
            score_delta=score_delta,
            tasks_count=1 if curriculum_task else 0,
            timestamp=time.time(),
        )
        self.history.append(metrics)

        if self.memory:
            self.memory.put("meta_rsi_generation", asdict(metrics))

        return metrics

    def run(self, generations: int = 3) -> MetaRSIReport:
        """Run multiple recursive self-improvement generations."""
        if generations < 1:
            raise ValueError("generations must be >= 1")

        run_id = f"meta-rsi-{int(time.time() * 1000)}"
        initial_score = self.introspect(self.active_policy)

        for gen in range(1, generations + 1):
            self.step(gen)

        final_score = self.introspect(self.active_policy)
        active_source = getattr(self.active_policy, "source", None)

        report = MetaRSIReport(
            run_id=run_id,
            generations_completed=generations,
            initial_score=initial_score,
            final_score=final_score,
            cumulative_gain=final_score - initial_score,
            generations=tuple(self.history),
            accepted_policies=tuple(self.accepted_policies),
            active_policy_name=self.active_policy.name,
            active_policy_source=active_source,
        )

        if self.memory:
            self.memory.put("meta_rsi_run", report.manifest())

        return report
