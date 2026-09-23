from __future__ import annotations
from dataclasses import dataclass, asdict
import json, time
from pathlib import Path
from typing import Any

from ..agents.coding import CodingTask
from ..agents.llm_discovery import LLMCodingDiscoveryAgent
from ..core.loop import DreamRSI
from ..evaluators.coding import CodeTestCase, CodingTestEvaluator
from ..execution.secure import SecurePythonExecutor
from ..llm.client import LLMClient
from ..policies.heuristic import ConservativePolicy
from ..policies.llm_developer import LLMPolicyDeveloper
from ..policies.registry import PolicyRegistry
from .fresh_validation import FreshValidator


@dataclass(frozen=True)
class FullRSIResult:
    task: str
    model: str
    iterations: int
    selected_policy: str
    best_fresh_score: float
    final_replay_score: float
    elapsed_s: float
    reports: list[dict[str, Any]]


def run_full_rsi(llm: LLMClient, task: CodingTask, tests: tuple[CodeTestCase, ...],
                 iterations: int = 3, workers: int = 2, online_rounds: int = 4,
                 replay_rounds: int = 20, fresh_rounds: int = 4, fresh_samples: int = 2,
                 executor=None) -> FullRSIResult:
    evaluator = CodingTestEvaluator(tests, sandbox=executor or SecurePythonExecutor())
    agent = LLMCodingDiscoveryAgent(llm, task)
    developer = LLMPolicyDeveloper(llm, PolicyRegistry())
    validator = FreshValidator(agent, evaluator=evaluator, workers=workers,
                               rounds=fresh_rounds, samples=fresh_samples)
    rsi = DreamRSI(agent=agent, policy_developer=developer,
                   policy=ConservativePolicy(beta=0.7), evaluator=evaluator,
                   fresh_validator=validator, workers=workers,
                   online_rounds=online_rounds, replay_rounds=replay_rounds,
                   min_fresh_delta=0.0)
    start = time.perf_counter()
    reports = []
    for i in range(1, iterations + 1):
        reports.append(asdict(rsi.run_iteration(i)))
    elapsed = time.perf_counter() - start
    fresh_scores = []
    for report in reports:
        for value in report.get("fresh_validation", {}).values():
            if isinstance(value, dict) and isinstance(value.get("score"), (int, float)):
                fresh_scores.append(float(value["score"]))
    return FullRSIResult(task.name, llm.model, iterations, rsi.policy.name,
                         max(fresh_scores) if fresh_scores else float("-inf"),
                         reports[-1]["best_replay_score"] if reports else float("-inf"),
                         elapsed, reports)


def save_full_rsi(path: str | Path, result: FullRSIResult) -> None:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(result), indent=2, ensure_ascii=False), encoding="utf-8")
