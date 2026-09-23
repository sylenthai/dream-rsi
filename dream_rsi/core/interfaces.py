from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Sequence, Mapping, Any


@dataclass(frozen=True)
class CandidateResult:
    score: float
    success: bool = True
    diagnostics: Mapping[str, Any] | None = None


class DiscoveryAgent(Protocol):
    def generate(self, parent_id: str, context: Mapping[str, Any]) -> CandidateResult: ...


class Evaluator(Protocol):
    def evaluate(self, candidate: CandidateResult) -> CandidateResult: ...


class ExplorationPolicy(Protocol):
    name: str
    def reset(self) -> None: ...
    def select_batch(self, tree_view: Any, max_parallelism: int) -> Sequence[str]: ...


class PolicyDeveloper(Protocol):
    def propose(self, current: ExplorationPolicy, feedback: Sequence[Mapping[str, Any]]) -> ExplorationPolicy: ...
