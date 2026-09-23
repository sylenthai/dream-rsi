from __future__ import annotations
import json
from typing import Any, Mapping
from ..core.interfaces import CandidateResult
from ..llm.client import LLMClient, extract_json
from ..agents.coding import CodingTask


class LLMCodingDiscoveryAgent:
    """Dream-RSI DiscoveryAgent backed by an LLM coding model.

    The agent generates code only; execution remains owned by the evaluator.
    Parent/tree context is compacted so the model observes the current prefix
    rather than hidden future nodes.
    """
    def __init__(self, llm: LLMClient, task: CodingTask):
        self.llm = llm
        self.task = task

    @staticmethod
    def _compact_tree(tree: Any, parent_id: str, limit: int = 24) -> dict[str, Any]:
        nodes = []
        current = parent_id
        path = []
        while current and current in tree.nodes and len(path) < limit:
            n = tree.nodes[current]
            path.append({"id": n.id, "depth": n.depth, "score": n.score,
                         "success": n.success, "diagnostics": {
                             k: v for k, v in n.diagnostics.items()
                             if k in {"passed", "total", "errors", "task_id"}
                         }})
            current = n.parent_id
        nodes.extend(reversed(path))
        return {"parent_id": parent_id, "path": nodes, "best_score": tree.best_score()}

    def generate(self, parent_id: str, context: Mapping[str, Any]) -> CandidateResult:
        tree = context.get("tree")
        compact = self._compact_tree(tree, parent_id) if tree is not None else {"parent_id": parent_id}
        system = (
            "You are the discovery agent inside a Dream-RSI coding research experiment. "
            "Return ONLY JSON with keys solution and explanation. solution is a complete Python "
            "program. Solve the task correctly and improve over the observed parent when possible. "
            "Do not use imports, network, subprocess, eval, exec, or filesystem access. "
            "Only observed prefix context is available; do not assume hidden nodes."
        )
        user = json.dumps({"task": self.task.prompt, "observed": compact}, ensure_ascii=False)
        response = self.llm.generate([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ], temperature=0.2, max_tokens=4096, response_format="json")
        data = extract_json(response.text)
        if not isinstance(data, dict) or not isinstance(data.get("solution"), str):
            raise ValueError("LLM response must contain a string 'solution'")
        return CandidateResult(float("nan"), True, {
            "artifact": data,
            "parent_id": parent_id,
            "model": self.llm.model,
            "task": self.task.name,
        })
