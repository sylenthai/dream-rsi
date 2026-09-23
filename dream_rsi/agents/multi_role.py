from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from typing import Any, Mapping
from ..llm.client import LLMClient, extract_json

@dataclass(frozen=True)
class RoleMessage:
    role: str
    content: str

@dataclass(frozen=True)
class AgentArtifact:
    role: str
    output: dict[str, Any]
    model: str

class MultiAgentResearchTeam:
    """Deterministic orchestration layer for Explorer/Coder/Reviewer/Tester/Researcher roles."""
    ROLES = ("explorer", "coder", "reviewer", "tester", "researcher")
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def _call(self, role: str, task: str, context: Mapping[str, Any]) -> AgentArtifact:
        system = (
            f"You are the {role} in a research coding team. Return ONLY valid JSON. "
            "Do not execute tools or code. Be concise, deterministic, evidence-based, "
            "and never invent test results."
        )
        prompt = json.dumps({"task": task, "context": dict(context)}, ensure_ascii=False)
        response = self.llm.generate([
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ], temperature=0.0, max_tokens=4096, response_format="json")
        data = extract_json(response.text)
        if not isinstance(data, dict):
            raise ValueError(f"{role}: expected JSON object")
        return AgentArtifact(role, data, self.llm.model)

    def run(self, task: str, context: Mapping[str, Any] | None = None) -> dict[str, AgentArtifact]:
        ctx = dict(context or {})
        out: dict[str, AgentArtifact] = {}
        for role in self.ROLES:
            artifact = self._call(role, task, {**ctx, "previous": {k: asdict(v) for k, v in out.items()}})
            out[role] = artifact
        return out
