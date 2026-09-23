from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..llm.client import LLMClient
from ..research.memory import ResearchMemoryStore
from .architect import EvolutionProposal, SelfArchitectAgent
from .introspector import CodebaseIntrospector, CodebaseMap
from .safety import SafetyGatekeeper, SafetyViolation


@dataclass(frozen=True)
class EvolutionCycleReport:
    cycle: int
    target_file: str
    rationale: str
    expected_benefit: str
    safety_passed: bool
    tests_passed: bool
    applied: bool
    error: str | None
    duration_s: float
    timestamp: float

    def manifest(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvolutionReport:
    run_id: str
    cycles_completed: int
    successful_evolutions: int
    failed_evolutions: int
    history: tuple[EvolutionCycleReport, ...]

    def manifest(self) -> dict[str, Any]:
        return asdict(self)


class AutonomousEvolutionEngine:
    """Supervised autonomous engine that inspects, designs, tests, and promotes code improvements."""

    def __init__(
        self,
        llm: LLMClient,
        repo_root: str | Path | None = None,
        memory: ResearchMemoryStore | None = None,
        safety: SafetyGatekeeper | None = None,
        auto_apply: bool = False,
    ):
        self.llm = llm
        if repo_root is None:
            # Default to root of the dream-rsi-3.3.1 package (parent of dream_rsi)
            repo_root = Path(__file__).resolve().parent.parent.parent
        self.repo_root = Path(repo_root).resolve()
        self.memory = memory or ResearchMemoryStore()
        self.safety = safety or SafetyGatekeeper()
        self.auto_apply = auto_apply
        self.introspector = CodebaseIntrospector(root=self.repo_root / "dream_rsi")
        self.architect = SelfArchitectAgent(self.llm)
        self.history: list[EvolutionCycleReport] = []

    def _verify_in_staging(self, proposal: EvolutionProposal) -> tuple[bool, str | None]:
        """Clone repository into an isolated staging sandbox, apply patch, and run test suite."""
        with tempfile.TemporaryDirectory(prefix="dream-rsi-evolution-staging-") as staging_dir:
            staging_path = Path(staging_dir)
            # Copy source code to staging, ignoring git caches and bytecode
            shutil.copytree(
                self.repo_root,
                staging_path / "repo",
                ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "runs", "artifacts"),
            )
            target = staging_path / "repo" / proposal.target_file
            if not target.parent.exists():
                target.parent.mkdir(parents=True, exist_ok=True)

            target.write_text(proposal.new_content, encoding="utf-8")

            # Run test suite inside staging directory, ignoring nested evolution test to prevent recursive runs
            env = dict(os.environ)
            env["DREAM_RSI_IN_STAGING"] = "1"

            if shutil.which("uv"):
                cmd = ["uv", "run", "--with", "pytest", "pytest", "-q", "--ignore=dream_rsi/tests/test_evolution.py", "dream_rsi/tests"]
            else:
                cmd = [sys.executable, "-m", "pytest", "-q", "--ignore=dream_rsi/tests/test_evolution.py", "dream_rsi/tests"]

            try:
                proc = subprocess.run(
                    cmd,
                    cwd=staging_path / "repo",
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=45,
                )
                if proc.returncode == 0:
                    return True, None
                error_msg = f"Regression tests failed (code {proc.returncode}):\n{proc.stdout[-500:]}\n{proc.stderr[-500:]}"
                return False, error_msg
            except subprocess.TimeoutExpired:
                return False, "Test suite execution timed out in staging sandbox"
            except Exception as exc:
                return False, f"Staging execution error: {type(exc).__name__}: {exc}"

    def step(self, cycle: int) -> EvolutionCycleReport:
        """Run a single autonomous codebase self-evolution cycle."""
        start_time = time.perf_counter()

        # 1. Read & introspect the entire codebase
        codebase_map = self.introspector.scan()

        # 2. Architect designs an improvement proposal
        try:
            proposal = self.architect.propose(codebase_map)
        except Exception as exc:
            duration = time.perf_counter() - start_time
            report = EvolutionCycleReport(
                cycle=cycle,
                target_file="none",
                rationale="Failed during proposal phase",
                expected_benefit="none",
                safety_passed=False,
                tests_passed=False,
                applied=False,
                error=f"Proposal error: {exc}",
                duration_s=duration,
                timestamp=time.time(),
            )
            self.history.append(report)
            return report

        # 3. Guardrail safety check (AST inspection, size budget, protected files)
        try:
            self.safety.inspect_patch(proposal.target_file, proposal.new_content)
            safety_passed = True
            safety_error = None
        except SafetyViolation as exc:
            safety_passed = False
            safety_error = str(exc)

        if not safety_passed:
            duration = time.perf_counter() - start_time
            report = EvolutionCycleReport(
                cycle=cycle,
                target_file=proposal.target_file,
                rationale=proposal.rationale,
                expected_benefit=proposal.expected_benefit,
                safety_passed=False,
                tests_passed=False,
                applied=False,
                error=f"Safety guardrail rejected patch: {safety_error}",
                duration_s=duration,
                timestamp=time.time(),
            )
            self.history.append(report)
            if self.memory:
                self.memory.put("evolution_safety_rejection", report.manifest())
            return report

        # 4. Sandboxed staging verification (Zero-Regression Rule)
        tests_passed, test_error = self._verify_in_staging(proposal)

        # 5. Atomic Promotion
        applied = False
        if tests_passed and self.auto_apply:
            real_target = self.repo_root / proposal.target_file
            real_target.parent.mkdir(parents=True, exist_ok=True)
            real_target.write_text(proposal.new_content, encoding="utf-8")
            applied = True

        duration = time.perf_counter() - start_time
        report = EvolutionCycleReport(
            cycle=cycle,
            target_file=proposal.target_file,
            rationale=proposal.rationale,
            expected_benefit=proposal.expected_benefit,
            safety_passed=True,
            tests_passed=tests_passed,
            applied=applied,
            error=test_error,
            duration_s=duration,
            timestamp=time.time(),
        )
        self.history.append(report)

        if self.memory:
            self.memory.put("evolution_cycle", report.manifest())

        return report

    def run(self, cycles: int = 2) -> EvolutionReport:
        """Run multiple autonomous self-evolution cycles."""
        run_id = f"evolve-{int(time.time() * 1000)}"
        for cycle in range(1, cycles + 1):
            self.step(cycle)

        successes = sum(1 for c in self.history if c.tests_passed)
        failures = len(self.history) - successes

        report = EvolutionReport(
            run_id=run_id,
            cycles_completed=cycles,
            successful_evolutions=successes,
            failed_evolutions=failures,
            history=tuple(self.history),
        )

        if self.memory:
            self.memory.put("evolution_run", report.manifest())

        return report
