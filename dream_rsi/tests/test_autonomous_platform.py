from __future__ import annotations

import json
from pathlib import Path

from dream_rsi.research.autonomous_platform import (
    AutonomousResearchConfig,
    AutonomousResearchController,
)
from dream_rsi.research.memory import ResearchMemoryStore
from dream_rsi.research.researcher import ExperimentPlan, Hypothesis


class FakeResearcher:
    def __init__(self):
        self.n = 0

    def propose(self, context):
        self.n += 1
        return Hypothesis(f"h{self.n}", "does method improve score?", "test", "higher", ("score",))

    def plan(self, hypothesis, available_tasks, methods, seeds, split="test"):
        return ExperimentPlan(hypothesis.id, split, (available_tasks[0],), (methods[0],), (seeds[0],), 1)

    def mutate(self, hypothesis, diagnosis, allowed_changes=None):
        raise AssertionError("mutation should not be needed for successful smoke")


def test_controller_runs_bounded_cycles_and_checkpoints(tmp_path: Path):
    memory = ResearchMemoryStore(tmp_path / "memory.sqlite3")
    checkpoint = tmp_path / "checkpoint.json"

    def runner(task, method, seed):
        return {"score": 0.75}

    controller = AutonomousResearchController(
        FakeResearcher(), runner, memory,
        AutonomousResearchConfig(
            max_cycles=2, max_experiments=4, max_workers=2,
            available_tasks=("task-a",), methods=("baseline",), seeds=(1,),
            checkpoint_path=str(checkpoint),
        ),
        run_id="test-run",
    )
    run = controller.run({"goal": "smoke"})
    assert len(run.cycles) == 2
    assert run.status == "succeeded"
    payload = json.loads(checkpoint.read_text())
    assert payload["run_id"] == "test-run"
    assert payload["status"] == "succeeded"
    assert memory.recent("autonomous_run", 1)


def test_controller_enforces_experiment_budget(tmp_path: Path):
    def runner(task, method, seed):
        return {"score": 1.0}

    controller = AutonomousResearchController(
        FakeResearcher(), runner, config=AutonomousResearchConfig(
            max_cycles=3, max_experiments=1, available_tasks=("a",), methods=("m",), seeds=(0,)
        )
    )
    run = controller.run({})
    assert len(run.cycles) == 1
    assert run.stop_reason == "experiment_budget_exhausted"
