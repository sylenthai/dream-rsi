from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Mapping, Sequence

from dream_rsi.repository.patching import PatchSet, apply_patchset
from dream_rsi.repository.runner import RepositoryRunner


@dataclass(frozen=True)
class BenchmarkTask:
    """Versioned repository benchmark task.

    The repository is a local snapshot supplied by the benchmark owner. The task
    never mutates that source tree: every trial receives a fresh workspace.
    """
    task_id: str
    repository: str
    prompt: str
    test_command: tuple[str, ...]
    split: str = "test"
    setup_command: tuple[str, ...] = ()
    timeout_s: float = 60.0
    tags: tuple[str, ...] = ()
    expected_base_fingerprint: str = ""

    def manifest(self) -> dict:
        return asdict(self)

    def validate(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")
        if not self.prompt.strip():
            raise ValueError("prompt must not be empty")
        if not self.test_command:
            raise ValueError("test_command must not be empty")
        if self.timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        if self.split not in {"train", "validation", "test", "held-out"}:
            raise ValueError(f"unsupported split: {self.split}")


@dataclass(frozen=True)
class BenchmarkResult:
    task_id: str
    success: bool
    returncode: int
    duration_s: float
    timed_out: bool
    mode: str
    changed_files: tuple[str, ...]
    repository_fingerprint: str
    stdout: str
    stderr: str
    benchmark_fingerprint: str
    secure_execution: bool

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryBenchmark:
    """Run a repository task against an isolated workspace.

    Docker is the preferred execution boundary. Local fallback is deliberately
    opt-in and is marked insecure in the returned evidence.
    """
    def __init__(self, *, prefer_docker: bool = True, allow_local_fallback: bool = False):
        self.prefer_docker = prefer_docker
        self.allow_local_fallback = allow_local_fallback

    @staticmethod
    def fingerprint_repository(path: str | Path) -> str:
        root = Path(path).resolve()
        h = hashlib.sha256()
        for p in sorted(
            x for x in root.rglob("*")
            if x.is_file() and ".git" not in x.parts and "__pycache__" not in x.parts
        ):
            h.update(str(p.relative_to(root)).encode())
            h.update(b"\0")
            h.update(p.read_bytes())
        return h.hexdigest()

    @staticmethod
    def fingerprint_task(task: BenchmarkTask) -> str:
        payload = json.dumps(task.manifest(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def _prepare(self, task: BenchmarkTask, patchset: PatchSet | None) -> tuple[tempfile.TemporaryDirectory, Path, tuple[str, ...]]:
        src = Path(task.repository).resolve()
        if not src.is_dir():
            raise FileNotFoundError(src)
        tmp = tempfile.TemporaryDirectory(prefix="dream-rsi-benchmark-")
        root = Path(tmp.name) / "repo"
        shutil.copytree(src, root, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        base = self.fingerprint_repository(root)
        if task.expected_base_fingerprint and base != task.expected_base_fingerprint:
            tmp.cleanup()
            raise ValueError("repository fingerprint does not match benchmark task")
        changed = tuple(apply_patchset(root, patchset)) if patchset else ()
        return tmp, root, changed

    def run(self, task: BenchmarkTask, patchset: PatchSet | None = None) -> BenchmarkResult:
        task.validate()
        tmp, root, changed = self._prepare(task, patchset)
        start = time.perf_counter()
        try:
            runner = RepositoryRunner(
                timeout_s=task.timeout_s,
                prefer_docker=self.prefer_docker,
                allow_local_fallback=self.allow_local_fallback,
            )
            if task.setup_command:
                setup = runner.run(root, task.setup_command)
                if not setup.success:
                    return BenchmarkResult(
                        task.task_id, False, setup.returncode, time.perf_counter() - start,
                        setup.timed_out, setup.mode, changed, setup.fingerprint,
                        setup.stdout, setup.stderr, self.fingerprint_task(task), setup.mode == "docker",
                    )
            result = runner.run(root, task.test_command)
            return BenchmarkResult(
                task_id=task.task_id,
                success=result.success,
                returncode=result.returncode,
                duration_s=time.perf_counter() - start,
                timed_out=result.timed_out,
                mode=result.mode,
                changed_files=changed,
                repository_fingerprint=result.fingerprint,
                stdout=result.stdout,
                stderr=result.stderr,
                benchmark_fingerprint=self.fingerprint_task(task),
                secure_execution=result.mode == "docker",
            )
        finally:
            tmp.cleanup()


class BenchmarkSuite:
    def __init__(self, tasks: Sequence[BenchmarkTask]):
        self.tasks = tuple(tasks)
        self._validate_unique()

    def _validate_unique(self) -> None:
        ids = [t.task_id for t in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("benchmark task IDs must be unique")
        for task in self.tasks:
            task.validate()

    def by_split(self, split: str) -> tuple[BenchmarkTask, ...]:
        return tuple(t for t in self.tasks if t.split == split)

    def manifest(self) -> dict:
        return {"version": "1.0", "tasks": [t.manifest() for t in self.tasks]}

    def fingerprint(self) -> str:
        payload = json.dumps(self.manifest(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.manifest(), indent=2, sort_keys=True), encoding="utf-8")
