from __future__ import annotations
from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Iterable
from ..agents.coding import CodingTask
from ..evaluators.coding import CodeTestCase

@dataclass(frozen=True)
class CodingBenchmarkTask:
    task: CodingTask
    tests: tuple[CodeTestCase, ...]
    tags: tuple[str, ...] = ()
    split: str = "test"
    difficulty: str = "medium"

    def manifest(self) -> dict:
        return {
            "name": self.task.name, "prompt": self.task.prompt,
            "tags": list(self.tags), "split": self.split,
            "difficulty": self.difficulty,
            "tests": [asdict(x) for x in self.tests],
        }

class TaskRegistry:
    def __init__(self, tasks: Iterable[CodingBenchmarkTask] = ()):
        self._tasks = {t.task.name: t for t in tasks}

    def add(self, task: CodingBenchmarkTask) -> None:
        if task.task.name in self._tasks:
            raise ValueError(f"duplicate task: {task.task.name}")
        self._tasks[task.task.name] = task

    def get(self, name: str) -> CodingBenchmarkTask:
        return self._tasks[name]

    def select(self, *, split: str | None = None, tag: str | None = None) -> tuple[CodingBenchmarkTask, ...]:
        values = tuple(self._tasks.values())
        if split is not None:
            values = tuple(t for t in values if t.split == split)
        if tag is not None:
            values = tuple(t for t in values if tag in t.tags)
        return values

    def save_manifest(self, path: str | Path) -> None:
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([t.manifest() for t in self._tasks.values()], indent=2), encoding="utf-8")


def default_coding_registry() -> TaskRegistry:
    tasks = [
        CodingBenchmarkTask(CodingTask("sum-two", "Read two integers from stdin and print their sum."),
                            (CodeTestCase("2 3\n", "5\n"), CodeTestCase("-4 9\n", "5\n")),
                            ("arithmetic", "smoke"), "test", "easy"),
        CodingBenchmarkTask(CodingTask("max-list", "Read n followed by n integers and print the maximum."),
                            (CodeTestCase("5\n1 8 3 2 7\n", "8\n"), CodeTestCase("3\n-5 -2 -9\n", "-2\n")),
                            ("arrays", "algorithmic"), "test", "medium"),
        CodingBenchmarkTask(CodingTask("count-vowels", "Read one line and print the number of English vowels aeiou, case-insensitive."),
                            (CodeTestCase("Hello World\n", "3\n"), CodeTestCase("XYZ\n", "0\n")),
                            ("strings", "algorithmic"), "held-out", "easy"),
    ]
    return TaskRegistry(tasks)
