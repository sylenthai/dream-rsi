from __future__ import annotations
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

@dataclass(frozen=True)
class ExecutionResult:
    returncode: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool = False

class PythonSandbox:
    """Small local sandbox boundary for trusted development machines.

    This is NOT a hardened security sandbox. For untrusted internet-scale code,
    replace it with a container/VM/seccomp/isolation service before deployment.
    """
    def __init__(self, timeout_s: float = 10.0, max_output_chars: int = 20_000):
        self.timeout_s = timeout_s
        self.max_output_chars = max_output_chars

    def run(self, code: str, args: list[str] | None = None, stdin: str | None = None) -> ExecutionResult:
        with tempfile.TemporaryDirectory(prefix="dream-rsi-") as workdir:
            path = os.path.join(workdir, "solution.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
            cmd = [sys.executable, "-I", "solution.py", *(args or [])]
            safe_env = {
                "PATH": os.environ.get("PATH", ""),
                "PYTHONNOUSERSITE": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            start = time.perf_counter()
            try:
                p = subprocess.run(
                    cmd,
                    cwd=workdir,
                    env=safe_env,
                    input=stdin,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_s,
                )
                timed_out = False
            except subprocess.TimeoutExpired as exc:
                return ExecutionResult(-1, (exc.stdout or "")[-self.max_output_chars:],
                                       (exc.stderr or "")[-self.max_output_chars:],
                                       time.perf_counter()-start, True)
            return ExecutionResult(p.returncode,
                                   p.stdout[-self.max_output_chars:],
                                   p.stderr[-self.max_output_chars:],
                                   time.perf_counter()-start, timed_out)
