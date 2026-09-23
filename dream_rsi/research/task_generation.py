from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, asdict
from typing import Any, Sequence
from ..agents.coding import CodingTask
from ..evaluators.coding import CodeTestCase
from ..llm.client import LLMClient, extract_json

@dataclass(frozen=True)
class GeneratedTask:
    task: CodingTask
    tests: tuple[CodeTestCase, ...]
    rationale: str
    source: str = "llm"
    parent_task: str | None = None
    difficulty: str = "medium"
    tags: tuple[str, ...] = ()
    def manifest(self) -> dict[str, Any]:
        d = asdict(self)
        d["tests"] = [asdict(x) for x in self.tests]
        return d

class FailureDrivenTaskGenerator:
    """Generates deterministic benchmark extensions from observed failures."""
    def __init__(self, llm: LLMClient, max_cases: int = 6):
        self.llm, self.max_cases = llm, max_cases
    def generate(self, task: str, failure: dict[str, Any], *, parent_task: str | None = None) -> GeneratedTask:
        prompt = {"task": task, "failure": failure, "requirements": {
            "new_task_name": "string", "prompt": "string",
            "tests": [{"stdin":"string","expected_stdout":"string","name":"string"}],
            "rationale":"string", "difficulty":"easy|medium|hard", "tags":["string"]}}
        system = ("You are a benchmark designer. Generate a small deterministic coding task that targets a failure. "
                  "Return ONLY JSON. Tests must be exact, deterministic, non-networked and runnable on Python stdin/stdout. "
                  "Do not claim execution results.")
        r = self.llm.generate([{"role":"system","content":system},{"role":"user","content":json.dumps(prompt)}],
                              temperature=0.0, max_tokens=3000, response_format="json")
        data = extract_json(r.text)
        tests = tuple(CodeTestCase(str(x.get("stdin","")), str(x.get("expected_stdout","")), str(x.get("name","case")))
                      for x in list(data.get("tests", []))[:self.max_cases])
        if not tests: raise ValueError("generated task has no tests")
        name = str(data.get("new_task_name") or "generated-" + hashlib.sha1(r.text.encode()).hexdigest()[:8])
        return GeneratedTask(CodingTask(name, str(data.get("prompt") or task)), tests,
                             str(data.get("rationale") or ""), parent_task=parent_task,
                             difficulty=str(data.get("difficulty") or "medium"),
                             tags=tuple(str(x) for x in data.get("tags", [])))
