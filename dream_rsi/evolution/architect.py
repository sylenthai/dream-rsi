from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from ..llm.client import LLMClient, extract_json
from .introspector import CodebaseMap


@dataclass(frozen=True)
class EvolutionProposal:
    target_file: str
    rationale: str
    expected_benefit: str
    new_content: str

    def manifest(self) -> dict[str, Any]:
        return asdict(self)


class SelfArchitectAgent:
    """Analyzes the codebase map and autonomously designs focused improvements."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def propose(self, codebase: CodebaseMap, focus: str = "performance_and_exploration") -> EvolutionProposal:
        summary = codebase.compact_summary(max_modules=25)
        system_prompt = (
            "You are an autonomous AI software architect improving the Dream-RSI codebase. "
            "You have reviewed the complete codebase structure below. "
            "Propose a concrete, focused, non-breaking improvement to ONE Python module. "
            "Return ONLY valid JSON matching this schema:\n"
            "{\n"
            '  "target_file": "relative/path/to/file.py",\n'
            '  "rationale": "Clear rationale for the improvement",\n'
            '  "expected_benefit": "Specific metric or behavioral gain",\n'
            '  "new_content": "Full, complete updated Python source code for the target_file"\n'
            "}\n"
            "Rules:\n"
            "1. Do not break existing API contracts.\n"
            "2. Keep the change bounded (under 250 lines).\n"
            "3. Do not modify protected files (e.g. pyproject.toml, policy.py).\n"
            "4. Never import forbidden modules like ctypes."
        )
        user_prompt = f"Focus: {focus}\n\n{summary}"

        response = self.llm.generate(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=6000,
            response_format="json",
        )

        data = extract_json(response.text)
        if not isinstance(data, dict):
            raise ValueError("Architect did not return a JSON object")

        target_file = str(data.get("target_file", "")).strip()
        new_content = str(data.get("new_content", ""))
        rationale = str(data.get("rationale", "Autonomous optimization"))
        expected_benefit = str(data.get("expected_benefit", "General improvement"))

        if not target_file or not new_content:
            raise ValueError("Architect proposal must include target_file and new_content")

        return EvolutionProposal(
            target_file=target_file,
            rationale=rationale,
            expected_benefit=expected_benefit,
            new_content=new_content,
        )
