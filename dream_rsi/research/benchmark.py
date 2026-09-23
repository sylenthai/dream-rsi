from __future__ import annotations
from dataclasses import dataclass, asdict
import json, time
@dataclass
class BenchmarkResult:
    name:str; iterations:int; wall_seconds:float; final_score:float; metadata:dict
    def to_json(self): return json.dumps(asdict(self),indent=2)
def run_benchmark(name, fn, iterations=3, metadata=None):
    t=time.perf_counter(); reports=fn(iterations); dt=time.perf_counter()-t
    score=reports[-1].best_replay_score if reports else float('-inf')
    return BenchmarkResult(name,iterations,dt,score,metadata or {})
