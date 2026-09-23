from __future__ import annotations
import os
from .docker_sandbox import DockerSandbox, DockerExecutionResult
from .python_sandbox import PythonSandbox
from .policy import ExecutionPolicy

class SecurePythonExecutor:
    """Policy-driven executor; local fallback is explicitly development-only."""
    def __init__(self, *, prefer_docker: bool = True, allow_local_fallback: bool | None = None,
                 policy: ExecutionPolicy | None = None, **docker_kwargs):
        self.policy = policy or ExecutionPolicy.from_env()
        self.docker = DockerSandbox(policy=self.policy, **docker_kwargs)
        self.local = PythonSandbox(self.policy.timeout_s, self.policy.max_output_chars)
        self.prefer_docker = prefer_docker
        if allow_local_fallback is None:
            production = os.getenv("DREAM_RSI_ENV", "development").lower() == "production"
            allow_local_fallback = not production
        self.allow_local_fallback = allow_local_fallback

    @property
    def mode(self) -> str:
        if self.prefer_docker and self.docker.available: return "docker"
        if self.allow_local_fallback: return "local-fallback"
        return "docker-unavailable"

    def run(self, code: str, args=None, stdin=None):
        if self.prefer_docker and self.docker.available:
            result = self.docker.run(code, args=args, stdin=stdin)
            if result.available:
                return result
            if not self.allow_local_fallback:
                return result
        if not self.allow_local_fallback:
            return DockerExecutionResult(-127, "", "Docker execution is unavailable and local fallback is disabled in production", 0.0, available=False)
        return self.local.run(code, args=args, stdin=stdin)
