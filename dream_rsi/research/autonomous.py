from __future__ import annotations
from dataclasses import dataclass, asdict
import json, time
from pathlib import Path
from typing import Any
from ..agents.coding import CodingTask
from ..evaluators.coding import CodeTestCase, CodingTestEvaluator
from ..execution.secure import SecurePythonExecutor
from ..llm.client import LLMClient
from ..policies.heuristic import ConservativePolicy
from ..policies.llm_developer import LLMPolicyDeveloper
from ..policies.registry import PolicyRegistry
from .full_rsi import run_full_rsi
from .memory import ResearchMemoryStore
from .task_generation import FailureDrivenTaskGenerator, GeneratedTask
from .task_registry import CodingBenchmarkTask, TaskRegistry

@dataclass(frozen=True)
class AutonomousCycle:
    cycle: int
    task: str
    score: float
    generated_task: dict[str, Any] | None
    experiment: dict[str, Any]

@dataclass(frozen=True)
class AutonomousResearchReport:
    model: str
    cycles: list[dict[str, Any]]
    memory_path: str
    elapsed_s: float

class AutonomousResearchLoop:
    """Closed research loop: run -> diagnose failure -> generate benchmark -> remember -> repeat."""
    def __init__(self, llm: LLMClient, memory: ResearchMemoryStore, registry: TaskRegistry):
        self.llm,self.memory,self.registry=llm,memory,registry
        self.generator=FailureDrivenTaskGenerator(llm)
    def run(self, initial: CodingBenchmarkTask, cycles: int = 3, **kwargs) -> AutonomousResearchReport:
        start=time.perf_counter(); current=initial; rows=[]
        for i in range(1,cycles+1):
            task_before = current
            result=run_full_rsi(self.llm,current.task,current.tests,**kwargs)
            row=asdict(result); score=float(result.best_fresh_score)
            self.memory.put("autonomous_cycle", {"cycle":i,"task":current.manifest(),"result":row})
            generated=None
            if score < 1.0:
                failure={"score":score,"reports":row.get("reports",[])[-1:]}
                try:
                    g=self.generator.generate(current.task.prompt,failure,parent_task=current.task.name)
                    generated=g.manifest(); self.memory.put("generated_task", generated)
                    next_task=CodingBenchmarkTask(g.task,g.tests,g.tags,"generated",g.difficulty)
                    if not any(t.task.name == next_task.task.name for t in self.registry.select()): self.registry.add(next_task)
                    current=next_task
                except Exception as exc:
                    self.memory.put("task_generation_error", {"cycle":i,"error":str(exc)})
            rows.append(asdict(AutonomousCycle(i,task_before.task.name,score,generated,row)))
        return AutonomousResearchReport(self.llm.model,rows,self.memory.path,time.perf_counter()-start)

def save_autonomous(path: str | Path, report: AutonomousResearchReport):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(asdict(report),indent=2,ensure_ascii=False),encoding="utf-8")
