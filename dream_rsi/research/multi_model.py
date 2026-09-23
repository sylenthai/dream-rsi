from __future__ import annotations
from dataclasses import dataclass, asdict
from statistics import mean, pstdev
from typing import Any, Callable, Iterable
import math, time

@dataclass(frozen=True)
class ModelTrial:
    model: str
    task: str
    seed: int
    score: float
    elapsed_s: float
    success: bool

@dataclass(frozen=True)
class ModelAggregate:
    model: str
    n: int
    mean_score: float
    std_score: float
    success_rate: float
    mean_elapsed_s: float

@dataclass(frozen=True)
class MultiModelReport:
    trials: list[dict[str, Any]]
    aggregates: list[dict[str, Any]]
    pairwise_deltas: dict[str, float]

class MultiModelResearchRunner:
    """Runs identical task/seed matrices and reports descriptive aggregates; no ranking is implied."""
    def __init__(self, experiment_fn: Callable[[str, str, int], Any]): self.experiment_fn = experiment_fn
    def run(self, models: Iterable[str], tasks: Iterable[str], seeds: Iterable[int]) -> MultiModelReport:
        trials=[]
        for model in models:
            for task in tasks:
                for seed in seeds:
                    t=time.perf_counter(); result=self.experiment_fn(model, task, seed); elapsed=time.perf_counter()-t
                    score=float(result if isinstance(result,(int,float)) else result.get("score",0.0))
                    trials.append(asdict(ModelTrial(model,task,seed,score,elapsed,score>=1.0)))
        ag=[]
        for model in dict.fromkeys(x["model"] for x in trials):
            xs=[x for x in trials if x["model"]==model]
            scores=[x["score"] for x in xs]
            ag.append(asdict(ModelAggregate(model,len(xs),mean(scores),pstdev(scores) if len(scores)>1 else 0.0,
                                             sum(x["success"] for x in xs)/len(xs),mean(x["elapsed_s"] for x in xs))))
        # Descriptive paired deltas relative to first model, without declaring a winner.
        base=next(iter(models),None); deltas={}
        if base:
            for other in dict.fromkeys(x["model"] for x in trials):
                if other==base: continue
                pairs={(x["task"],x["seed"]):x["score"] for x in trials if x["model"]==base}
                ys={(x["task"],x["seed"]):x["score"] for x in trials if x["model"]==other}
                common=set(pairs)&set(ys)
                deltas[f"{other}-vs-{base}"]=mean([ys[k]-pairs[k] for k in common]) if common else math.nan
        return MultiModelReport(trials,ag,deltas)
