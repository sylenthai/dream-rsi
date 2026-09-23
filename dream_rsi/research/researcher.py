from __future__ import annotations
from dataclasses import dataclass, asdict
import json
import time
from typing import Any, Callable, Iterable

from ..llm.client import LLMClient, extract_json
from .memory import ResearchMemoryStore


@dataclass(frozen=True)
class Hypothesis:
    id: str
    question: str
    rationale: str
    expected_effect: str
    metrics: tuple[str, ...]
    constraints: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResearchMutation:
    id: str
    parent_hypothesis_id: str
    trigger: str
    change: str
    expected_effect: str
    constraints: tuple[str, ...] = ()

@dataclass(frozen=True)
class ExperimentPlan:
    hypothesis_id: str
    benchmark_split: str
    tasks: tuple[str, ...]
    methods: tuple[str, ...]
    seeds: tuple[int, ...]
    repetitions: int = 1

class LLMResearcher:
    """Structured hypothesis generator/planner with persistent research memory."""
    def __init__(self, llm: LLMClient, memory: ResearchMemoryStore | None = None):
        self.llm = llm
        self.memory = memory

    def _ask_json(self, system: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.llm.generate(
            [{"role": "system", "content": system},
             {"role": "user", "content": json.dumps(payload, sort_keys=True)}],
            temperature=0.2, max_tokens=1800, response_format="json")
        data = extract_json(response.text)
        if not isinstance(data, dict):
            raise ValueError("researcher response must be a JSON object")
        return data

    def propose(self, context: dict[str, Any]) -> Hypothesis:
        data = self._ask_json(
            "Generate exactly one falsifiable ML/agent research hypothesis. Return JSON with id, question, rationale, expected_effect, metrics, constraints. Do not invent measured results.",
            {"context": context, "memory": self.memory.summary(20) if self.memory else {}})
        h = Hypothesis(
            str(data["id"]), str(data["question"]), str(data["rationale"]),
            str(data["expected_effect"]), tuple(map(str, data.get("metrics", []))),
            tuple(map(str, data.get("constraints", []))))
        if self.memory:
            self.memory.put("hypothesis", asdict(h))
        return h

    def mutate(self, hypothesis: Hypothesis, diagnosis: dict[str, Any], allowed_changes: list[str] | None = None) -> ResearchMutation:
        data = self._ask_json(
            "Propose exactly one conservative research-strategy mutation based only on the supplied diagnosis. Return JSON with id, parent_hypothesis_id, trigger, change, expected_effect, constraints. Never claim an unmeasured improvement. Choose change from allowed_changes when supplied.",
            {"hypothesis": asdict(hypothesis), "diagnosis": diagnosis, "allowed_changes": allowed_changes or []})
        change = str(data["change"])
        if allowed_changes and change not in allowed_changes:
            raise ValueError("research mutation selected a change outside the allowed strategy space")
        mutation = ResearchMutation(str(data["id"]), hypothesis.id, str(data["trigger"]), change, str(data["expected_effect"]), tuple(map(str, data.get("constraints", []))))
        if self.memory:
            self.memory.put("research_mutation", asdict(mutation))
        return mutation

    def plan(self, hypothesis: Hypothesis, available_tasks: list[str], methods: list[str], seeds: list[int], split: str = "test") -> ExperimentPlan:
        data = self._ask_json(
            "Turn a hypothesis into a minimal reproducible experiment plan. Only choose from supplied tasks, methods and seeds. Return JSON with tasks, methods, seeds, repetitions.",
            {"hypothesis": asdict(hypothesis), "available_tasks": available_tasks,
             "methods": methods, "seeds": seeds, "split": split})
        task_set, method_set, seed_set = set(available_tasks), set(methods), set(seeds)
        tasks = tuple(str(x) for x in data.get("tasks", []))
        selected_methods = tuple(str(x) for x in data.get("methods", []))
        selected_seeds = tuple(int(x) for x in data.get("seeds", []))
        if not tasks or not set(tasks) <= task_set or not set(selected_methods) <= method_set or not set(selected_seeds) <= seed_set:
            raise ValueError("research plan selected values outside the allowed experiment space")
        plan = ExperimentPlan(hypothesis.id, split, tasks, selected_methods, selected_seeds, max(1, int(data.get("repetitions", 1))))
        if self.memory:
            self.memory.put("experiment_plan", asdict(plan))
        return plan
