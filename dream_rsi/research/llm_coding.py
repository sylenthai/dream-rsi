from __future__ import annotations
from dataclasses import dataclass, asdict
import json, time
from pathlib import Path
from typing import Any

from ..agents.coding import CodingTask, LLMCodeAgent
from ..core.interfaces import CandidateResult
from ..core.tree import DiscoveryTree
from ..evaluators.coding import CodeTestCase, CodingTestEvaluator
from ..llm.client import LLMClient


@dataclass(frozen=True)
class CodingExperimentResult:
    task: str
    model: str
    iterations: int
    best_score: float
    final_score: float
    total_seconds: float
    generated_candidates: int
    successful_candidates: int
    best_solution: str = ""
    diagnostics: dict[str, Any] | None = None


class IterativeLLMCodingHarness:
    """A real LLM coding benchmark with reproducible evaluation.

    This is the bridge between the research benchmark and Dream-RSI's tree:
    every generated solution is evaluated independently and retained in a tree.
    It does not execute model code outside the CodingTestEvaluator boundary.
    """
    def __init__(self, llm: LLMClient, task: CodingTask,
                 tests: tuple[CodeTestCase, ...], *, evaluator: CodingTestEvaluator | None = None):
        self.agent = LLMCodeAgent(llm, task)
        self.task = task
        self.evaluator = evaluator or CodingTestEvaluator(tests)
        self.tree = DiscoveryTree()
        self.llm = llm

    def _evaluate_artifact(self, artifact: dict[str, Any], parent_id: str) -> CandidateResult:
        raw = CandidateResult(float("nan"), True, {"artifact": artifact, "parent_id": parent_id, "model": self.llm.model})
        return self.evaluator.evaluate(raw)

    def run(self, iterations: int = 5) -> CodingExperimentResult:
        start = time.perf_counter()
        successful = 0
        best = float("-inf")
        best_solution = ""
        feedback: list[dict[str, Any]] = []
        for i in range(iterations):
            parent_id = "root" if i == 0 else max(self.tree.nodes, key=lambda n: self.tree.nodes[n].score if self.tree.nodes[n].score is not None else float("-inf"))
            context = {"iteration": i + 1, "feedback": feedback[-3:], "tree_best_score": self.tree.best_score()}
            try:
                artifact = self.agent.generate_artifact(context)
                result = self._evaluate_artifact(artifact, parent_id)
            except Exception as exc:
                artifact = {"solution": "", "explanation": "generation error"}
                result = CandidateResult(float("-inf"), False, {"error": str(exc), "artifact": artifact})
            node = self.tree.add_child(parent_id, result.score, result.success, dict(result.diagnostics or {}))
            if result.success:
                successful += 1
            if result.score > best:
                best = result.score
                best_solution = artifact.get("solution", "")
            feedback.append({"iteration": i + 1, "score": result.score, "success": result.success,
                             "errors": (result.diagnostics or {}).get("errors", [])})
        elapsed = time.perf_counter() - start
        return CodingExperimentResult(self.task.name, self.llm.model, iterations, best, result.score,
                                      elapsed, iterations, successful, best_solution,
                                      {"tree_nodes": len(self.tree.nodes), "feedback": feedback})


def save_result(path: str | Path, result: CodingExperimentResult) -> None:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(result), indent=2, ensure_ascii=False), encoding="utf-8")
