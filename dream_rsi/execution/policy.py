from __future__ import annotations
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class ExecutionPolicy:
    """Explicit security/resource policy for untrusted execution."""
    network: bool = False
    read_only_root: bool = True
    no_new_privileges: bool = True
    drop_all_capabilities: bool = True
    memory: str = "256m"
    cpus: str = "1.0"
    pids_limit: int = 64
    tmpfs_size: str = "32m"
    timeout_s: float = 10.0
    max_output_chars: int = 20_000

    @classmethod
    def from_env(cls) -> "ExecutionPolicy":
        policy = cls(
            network=os.getenv("DREAM_RSI_EXEC_NETWORK", "none").lower() in {"1", "true", "yes"},
            read_only_root=os.getenv("DREAM_RSI_EXEC_READONLY", "1").lower() not in {"0", "false", "no"},
            memory=os.getenv("DREAM_RSI_EXEC_MEMORY", cls.memory),
            cpus=os.getenv("DREAM_RSI_EXEC_CPUS", cls.cpus),
            pids_limit=int(os.getenv("DREAM_RSI_EXEC_PIDS", cls.pids_limit)),
            tmpfs_size=os.getenv("DREAM_RSI_EXEC_TMPFS", cls.tmpfs_size),
            timeout_s=float(os.getenv("DREAM_RSI_EXEC_TIMEOUT", cls.timeout_s)),
            max_output_chars=int(os.getenv("DREAM_RSI_EXEC_MAX_OUTPUT", cls.max_output_chars)),
        )
        # Environment overrides must satisfy the same invariants as explicit constructor values.
        policy.validate()
        return policy

    def validate(self) -> None:
        if self.pids_limit < 1 or self.pids_limit > 4096:
            raise ValueError("pids_limit must be between 1 and 4096")
        if self.timeout_s <= 0 or self.timeout_s > 3600:
            raise ValueError("timeout_s must be in (0, 3600]")
        if self.max_output_chars < 256 or self.max_output_chars > 10_000_000:
            raise ValueError("max_output_chars is outside the allowed range")
