from __future__ import annotations
from dataclasses import dataclass, asdict
from statistics import mean, median, pstdev
from typing import Iterable

@dataclass(frozen=True)
class ExperimentMetrics:
    final_score: float
    best_score: float
    median_score: float
    std_score: float
    successful_trials: int
    total_trials: int
    success_rate: float
    policy_changes: int
    candidate_rejections: int
    elapsed_s: float

    def to_dict(self): return asdict(self)

def summarize(scores: Iterable[float], *, elapsed_s: float = 0.0,
              policy_changes: int = 0, candidate_rejections: int = 0) -> ExperimentMetrics:
    xs = [float(x) for x in scores]
    if not xs:
        return ExperimentMetrics(float("-inf"), float("-inf"), float("-inf"), 0.0, 0, 0, 0.0,
                                 policy_changes, candidate_rejections, elapsed_s)
    successes = sum(x >= 1.0 for x in xs)
    return ExperimentMetrics(xs[-1], max(xs), median(xs), pstdev(xs) if len(xs) > 1 else 0.0,
                             successes, len(xs), successes / len(xs), policy_changes,
                             candidate_rejections, elapsed_s)
