from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Protocol
import json, os, time, urllib.error, urllib.request
from .policy import ExecutionPolicy

@dataclass(frozen=True)
class MicroVMExecutionResult:
    returncode: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool = False
    backend: str = "microvm"

class MicroVMBackend(Protocol):
    def run(self, code: str, *, args: list[str] | None = None, stdin: str | None = None,
            policy: ExecutionPolicy | None = None) -> MicroVMExecutionResult: ...

class FirecrackerBackend:
    """Integration boundary for a Firecracker/gVisor service.

    This communicates over an HTTP RPC boundary with a separately deployed
    privileged microVM worker service.
    """
    def __init__(self, endpoint: str | None = None, timeout: float = 30.0):
        self.endpoint = endpoint or os.getenv("DREAM_RSI_MICROVM_ENDPOINT")
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.endpoint)

    def run(self, code: str, *, args: list[str] | None = None, stdin: str | None = None,
            policy: ExecutionPolicy | None = None) -> MicroVMExecutionResult:
        if not self.configured:
            raise RuntimeError("Firecracker backend is not configured; deploy the privileged microVM worker")
        payload = {
            "code": code,
            "args": args or [],
            "stdin": stdin,
            "policy": asdict(policy) if policy else None,
        }
        req = urllib.request.Request(
            f"{self.endpoint.rstrip('/')}/run",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return MicroVMExecutionResult(
                    returncode=data.get("returncode", 0),
                    stdout=data.get("stdout", ""),
                    stderr=data.get("stderr", ""),
                    duration_s=float(data.get("duration_s", time.perf_counter() - start)),
                    timed_out=bool(data.get("timed_out", False)),
                )
        except urllib.error.HTTPError as exc:
            return MicroVMExecutionResult(
                returncode=-1,
                stdout="",
                stderr=f"MicroVM RPC HTTP error: {exc.code} {exc.reason}",
                duration_s=time.perf_counter() - start,
            )
        except Exception as exc:
            return MicroVMExecutionResult(
                returncode=-1,
                stdout="",
                stderr=f"MicroVM RPC connection error: {type(exc).__name__}: {exc}",
                duration_s=time.perf_counter() - start,
            )
