from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Mapping
from ..core.interfaces import CandidateResult
from ..llm.client import LLMClient, extract_json

@dataclass(frozen=True)
class CodingTask:
    name: str
    prompt: str
    test_command: str = "python solution.py"

class LLMCodeAgent:
    """Generate one self-contained candidate artifact using an LLM.

    Execution is deliberately separated from generation: this class never executes
    model-produced code. The executor/evaluator owns that security boundary.
    """
    def __init__(self, llm: LLMClient, task: CodingTask):
        self.llm, self.task = llm, task

    def generate_artifact(self, parent_context: Mapping[str, Any]) -> dict[str, Any]:
        system = (
            "You are a code discovery agent. Return ONLY valid JSON with keys "
            "solution, explanation. solution must be a complete Python program "
            "saved as solution.py. Do not use network, subprocess, os.system, "
            "eval, exec, or filesystem access outside the working directory."
        )
        user = json.dumps({
            "task": self.task.prompt,
            "parent_context": dict(parent_context),
        }, ensure_ascii=False)
        response = self.llm.generate([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ], temperature=0.2, max_tokens=4096, response_format="json")
        data = extract_json(response.text)
        if not isinstance(data, dict) or not isinstance(data.get("solution"), str):
            raise ValueError("LLM response must contain a string 'solution'")
        return data

    def generate(self, parent_id: str, context: Mapping[str, Any]) -> CandidateResult:
        artifact = self.generate_artifact(context)
        return CandidateResult(
            score=float("nan"), success=True,
            diagnostics={"artifact": artifact, "parent_id": parent_id, "model": self.llm.model},
        )
