from __future__ import annotations
import shutil, subprocess, tempfile, time
from dataclasses import dataclass
from pathlib import Path
from .policy import ExecutionPolicy

@dataclass(frozen=True)
class DockerExecutionResult:
    returncode: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool = False
    available: bool = True
    backend: str = "docker"

DAEMON_ERROR_PATTERNS = (
    "cannot connect to the docker daemon",
    "is the docker daemon running",
    "dockerdesktoplinuxengine",
    "error during connect",
    "dial unix",
    "open //./pipe/docker",
)

class DockerSandbox:
    """Docker execution boundary with explicit deny-by-default security policy."""
    def __init__(self, timeout_s: float = 10.0, max_output_chars: int = 20_000,
                 image: str | None = None, memory: str = "256m",
                 cpus: str = "1.0", pids_limit: int = 64, policy: ExecutionPolicy | None = None):
        import os
        self.policy = policy or ExecutionPolicy(timeout_s=timeout_s, max_output_chars=max_output_chars,
                                                memory=memory, cpus=cpus, pids_limit=pids_limit)
        self.policy.validate()
        self.image = image or os.getenv("DREAM_RSI_DOCKER_IMAGE", "python:3.12-alpine")

    @property
    def available(self) -> bool:
        return shutil.which("docker") is not None

    def run(self, code: str, args: list[str] | None = None, stdin: str | None = None) -> DockerExecutionResult:
        if not self.available:
            return DockerExecutionResult(-127, "", "docker executable not found", 0.0, available=False)
        with tempfile.TemporaryDirectory(prefix="dream-rsi-docker-") as tmp:
            workdir = Path(tmp)
            workdir.chmod(0o755)
            sol = workdir / "solution.py"
            sol.write_text(code, encoding="utf-8")
            sol.chmod(0o644)
            network = "default" if self.policy.network else "none"
            cmd = ["docker", "run", "--rm", "--network", network]
            if self.policy.read_only_root: cmd += ["--read-only"]
            if self.policy.drop_all_capabilities: cmd += ["--cap-drop", "ALL"]
            if self.policy.no_new_privileges: cmd += ["--security-opt", "no-new-privileges"]
            cmd += ["--pids-limit", str(self.policy.pids_limit), "--memory", self.policy.memory,
                    "--cpus", self.policy.cpus, "--tmpfs", f"/tmp:rw,noexec,nosuid,size={self.policy.tmpfs_size}",
                    "--mount", f"type=bind,src={workdir},dst=/workspace,readonly",
                    self.image, "python", "/workspace/solution.py", *(args or [])]
            start = time.perf_counter()
            try:
                p = subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=self.policy.timeout_s)
            except subprocess.TimeoutExpired as exc:
                return DockerExecutionResult(-1, (exc.stdout or "")[-self.policy.max_output_chars:],
                                              (exc.stderr or "")[-self.policy.max_output_chars:],
                                              time.perf_counter()-start, True)
            duration = time.perf_counter() - start
            stderr = p.stderr[-self.policy.max_output_chars:]
            stdout = p.stdout[-self.policy.max_output_chars:]
            is_daemon_error = p.returncode != 0 and any(pat in stderr.lower() for pat in DAEMON_ERROR_PATTERNS)
            if is_daemon_error:
                return DockerExecutionResult(p.returncode, stdout, stderr, duration, available=False)
            return DockerExecutionResult(p.returncode, stdout, stderr, duration)
