from __future__ import annotations

from dataclasses import dataclass, asdict, replace
import csv
import json
import math
import random
import statistics
import time
from pathlib import Path
from typing import Any

from ..core.loop import DreamRSI
from ..policies.heuristic import ConservativePolicy
from ..policies.mutator import PolicyMutator
from .fresh_validation import FreshValidator
from .tasks import DiscoveryTask, TaskAwareToyAgent, default_task_suite, get_split


@dataclass(frozen=True)
class TrialResult:
    # Keep the existing positional constructor stable. New experiment
    # dimensions are appended with defaults for backward compatibility.
    method: str
    seed: int
    final_score: float
    final_replay_score: float
    selected_policy: str
    iterations: int
    wall_seconds: float
    split: str = "test"
    task_id: str = "default"


@dataclass(frozen=True)
class Summary:
    method: str
    split: str
    n: int
    mean: float
    std: float
    median: float
    ci95_low: float
    ci95_high: float
    min: float
    max: float

    def to_dict(self):
        return asdict(self)


class StaticDeveloper:
    def propose(self, current, feedback):
        return current


class RandomPolicy(ConservativePolicy):
    name = "random"

    def __init__(self, seed: int = 0):
        super().__init__(beta=0.7)
        self.rng = random.Random(seed)

    def reset(self):
        pass

    def select_batch(self, view, max_parallelism):
        eligible = list(view.eligible())
        self.rng.shuffle(eligible)
        return eligible[:max_parallelism]


def _make_engine(seed: int, method: str, task: DiscoveryTask, workers: int, rounds: int) -> DreamRSI:
    agent = TaskAwareToyAgent(task, seed=seed)
    if method in {"dream-rsi", "no-fresh-gate"}:
        validator = None if method == "no-fresh-gate" else FreshValidator(
            TaskAwareToyAgent(task, seed=seed + 100_000), workers=workers, rounds=rounds,
            samples=3,
        )
        return DreamRSI(
            agent, PolicyMutator(), ConservativePolicy(0.35), fresh_validator=validator,
            workers=workers, online_rounds=rounds, replay_rounds=rounds * 4,
            min_fresh_delta=0.0,
        )
    if method == "replay-only":
        return DreamRSI(agent, PolicyMutator(), ConservativePolicy(0.35), workers=workers,
                        online_rounds=rounds, replay_rounds=rounds * 4)
    if method == "static":
        return DreamRSI(agent, StaticDeveloper(), ConservativePolicy(0.35), workers=workers,
                        online_rounds=rounds, replay_rounds=rounds * 4)
    if method == "random":
        return DreamRSI(agent, StaticDeveloper(), RandomPolicy(seed), workers=workers,
                        online_rounds=rounds, replay_rounds=rounds * 4)
    raise ValueError(f"unknown method: {method}")


def run_trials(
    methods: list[str],
    seeds: list[int],
    iterations: int = 5,
    workers: int = 4,
    rounds: int = 8,
    split: str = "test",
    tasks: tuple[DiscoveryTask, ...] | None = None,
) -> list[TrialResult]:
    suite = default_task_suite()
    selected_tasks = tasks or get_split(suite, split)
    out: list[TrialResult] = []
    for task in selected_tasks:
        for seed in seeds:
            for method in methods:
                engine = _make_engine(seed, method, task, workers, rounds)
                t0 = time.perf_counter()
                reports = [engine.run_iteration(i) for i in range(1, iterations + 1)]
                elapsed = time.perf_counter() - t0
                final = reports[-1] if reports else None
                selected = engine.policy
                evaluator = FreshValidator(
                    TaskAwareToyAgent(task, seed=seed + 200_000),
                    workers=workers, rounds=rounds, samples=5,
                )
                fresh = evaluator.validate(selected)
                out.append(TrialResult(
                    method=method, seed=seed, final_score=fresh.score,
                    final_replay_score=final.best_replay_score if final else float("nan"),
                    selected_policy=final.selected_policy if final else "",
                    iterations=iterations, wall_seconds=elapsed,
                    split=split, task_id=task.task_id,
                ))
    return out


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def summarize(results: list[TrialResult]) -> list[Summary]:
    by_method: dict[tuple[str, str], list[float]] = {}
    for r in results:
        by_method.setdefault((r.method, r.split), []).append(r.final_score)
    out = []
    z = statistics.NormalDist().inv_cdf(0.975)
    for (method, split), values in sorted(by_method.items()):
        n = len(values)
        mean = statistics.fmean(values)
        std = statistics.stdev(values) if n > 1 else 0.0
        margin = z * std / math.sqrt(n) if n > 1 else 0.0
        out.append(Summary(method, split, n, mean, std, statistics.median(values),
                           mean - margin, mean + margin, min(values), max(values)))
    return out


def paired_differences(results: list[TrialResult], method_a: str, method_b: str) -> list[float]:
    a = {(r.task_id, r.seed): r.final_score for r in results if r.method == method_a}
    b = {(r.task_id, r.seed): r.final_score for r in results if r.method == method_b}
    common = sorted(a.keys() & b.keys())
    return [a[k] - b[k] for k in common]


def paired_permutation_pvalue(diffs: list[float], exact_limit: int = 16, permutations: int = 50_000, seed: int = 12345) -> float:
    if not diffs:
        return float("nan")
    observed = abs(statistics.fmean(diffs))
    n = len(diffs)
    rng = random.Random(seed)
    if n <= exact_limit:
        total = 1 << n
        extreme = 0
        for mask in range(total):
            s = sum(-d if (mask >> i) & 1 else d for i, d in enumerate(diffs))
            if abs(s / n) >= observed - 1e-15:
                extreme += 1
        return extreme / total
    extreme = 0
    for _ in range(permutations):
        s = sum((-d if rng.getrandbits(1) else d) for d in diffs)
        if abs(s / n) >= observed:
            extreme += 1
    return (extreme + 1) / (permutations + 1)


def paired_bootstrap_ci(diffs: list[float], samples: int = 20_000, seed: int = 12345) -> tuple[float, float]:
    if not diffs:
        return float("nan"), float("nan")
    rng = random.Random(seed)
    n = len(diffs)
    means = [statistics.fmean(diffs[rng.randrange(n)] for _ in range(n)) for _ in range(samples)]
    return _quantile(means, 0.025), _quantile(means, 0.975)


def compare(results: list[TrialResult], method_a: str, method_b: str) -> dict[str, Any]:
    diffs = paired_differences(results, method_a, method_b)
    ci = paired_bootstrap_ci(diffs)
    return {
        "method_a": method_a,
        "method_b": method_b,
        "n_pairs": len(diffs),
        "mean_difference_a_minus_b": statistics.fmean(diffs) if diffs else float("nan"),
        "bootstrap_ci95_low": ci[0],
        "bootstrap_ci95_high": ci[1],
        "paired_permutation_p": paired_permutation_pvalue(diffs),
        "positive_difference_rate": (sum(d > 0 for d in diffs) / len(diffs)) if diffs else float("nan"),
    }


def save_report(path: str | Path, results: list[TrialResult], summaries: list[Summary], comparisons: list[dict[str, Any]], *, protocol: dict[str, Any] | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "protocol_version": "2.0",
        "protocol": protocol or {},
        "trials": [asdict(x) for x in results],
        "summaries": [x.to_dict() for x in summaries],
        "comparisons": comparisons,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def save_csv(path: str | Path, results: list[TrialResult]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [asdict(x) for x in results]
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
