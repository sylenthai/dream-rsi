from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
from dataclasses import dataclass


@dataclass(frozen=True)
class ExecResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool


class PythonExecutor:
    """Process isolation with timeout and limited environment.

    Note: This is intended for trusted/development workloads, not a hostile-code boundary.
    For untrusted or hostile model-generated code, use isolated containers or microVMs.
    """

    def __init__(self, timeout_s: float = 10.0, max_output_bytes: int = 64000):
        self.timeout_s = timeout_s
        self.max_output_bytes = max_output_bytes

    def run(self, code: str) -> ExecResult:
        with tempfile.TemporaryDirectory(prefix="dream-rsi-") as td:
            script_path = Path(td) / "solution.py"
            script_path.write_text(code, encoding="utf-8")
            env = {
                "PATH": os.environ.get("PATH", ""),
                "PYTHONNOUSERSITE": "1",
            }
            try:
                result = subprocess.run(
                    [sys.executable, "-I", str(script_path)],
                    cwd=td,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_s,
                )
                return ExecResult(
                    returncode=result.returncode,
                    stdout=result.stdout[:self.max_output_bytes],
                    stderr=result.stderr[:self.max_output_bytes],
                    timed_out=False,
                )
            except subprocess.TimeoutExpired as exc:
                stdout_str = exc.stdout if isinstance(exc.stdout, str) else ""
                stderr_str = exc.stderr if isinstance(exc.stderr, str) else ""
                return ExecResult(
                    returncode=-1,
                    stdout=stdout_str[:self.max_output_bytes],
                    stderr=stderr_str[:self.max_output_bytes],
                    timed_out=True,
                )
