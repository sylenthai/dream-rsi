from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from typing import Any, Iterable

from ..core.interfaces import CandidateResult
from ..execution.python_sandbox import PythonSandbox
from ..execution.secure import SecurePythonExecutor


@dataclass(frozen=True)
class CodeTestCase:
    stdin: str
    expected_stdout: str
    name: str = "case"


@dataclass(frozen=True)
class CodeEvaluation:
    passed: int
    total: int
    score: float
    duration_s: float
    errors: tuple[str, ...]


class CodingTestEvaluator:
    """Evaluate generated Python against deterministic stdin/stdout cases.

    This evaluator is intentionally simple and reproducible. It is a benchmark
    adapter, not a hardened security boundary; use an isolated container/VM for
    untrusted model-generated code.
    """

    def __init__(self, tests: Iterable[CodeTestCase], sandbox: PythonSandbox | SecurePythonExecutor | None = None):
        self.tests = tuple(tests)
        self.sandbox = sandbox or SecurePythonExecutor(prefer_docker=True, allow_local_fallback=None)

    @staticmethod
    def _validate_source(code: str) -> str | None:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return f"syntax: {exc}"
        banned = (ast.Import, ast.ImportFrom)
        if any(isinstance(node, banned) for node in ast.walk(tree)):
            return "imports are disabled"
        return None

    @staticmethod
    def _normalize(value: str) -> str:
        return "\n".join(line.rstrip() for line in value.strip().splitlines())

    def evaluate(self, candidate: CandidateResult) -> CandidateResult:
        artifact = (candidate.diagnostics or {}).get("artifact", {})
        code = artifact.get("solution") if isinstance(artifact, dict) else None
        if not isinstance(code, str):
            return CandidateResult(-math.inf, False, {"error": "missing solution"})
        error = self._validate_source(code)
        if error:
            return CandidateResult(-math.inf, False, {"error": error})

        passed = 0
        errors: list[str] = []
        total_duration = 0.0
        for case in self.tests:
            result = self.sandbox.run(code, stdin=case.stdin)
            total_duration += result.duration_s
            if result.timed_out:
                errors.append(f"{case.name}: timeout")
                continue
            if result.returncode != 0:
                errors.append(f"{case.name}: returncode={result.returncode}: {result.stderr[:300]}")
                continue
            if self._normalize(result.stdout) == self._normalize(case.expected_stdout):
                passed += 1
            else:
                errors.append(
                    f"{case.name}: expected={case.expected_stdout!r} got={result.stdout!r}"
                )

        total = len(self.tests)
        score = passed / total if total else 0.0
        success = total > 0 and passed == total
        return CandidateResult(score, success, {
            "passed": passed,
            "total": total,
            "score": score,
            "duration_s": total_duration,
            "errors": errors,
            "artifact": artifact,
        })
