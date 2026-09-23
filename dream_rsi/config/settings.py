from __future__ import annotations
from dataclasses import dataclass, field
import os

@dataclass(frozen=True)
class Settings:
    db_path: str = "runs/dream_rsi.sqlite3"
    artifact_dir: str = "runs/artifacts"
    workers: int = 4
    online_rounds: int = 20
    replay_rounds: int = 100
    fresh_validation_rounds: int = 1
    beta1: float = 0.01
    beta2: float = 0.02
    execution_timeout_s: float = 10.0
    max_output_bytes: int = 64_000
    max_candidates: int = 4
    random_seed: int = 42
    provider: str = "toy"

    @classmethod
    def from_env(cls) -> "Settings":
        def integer(k, d): return int(os.getenv(k, d))
        def number(k, d): return float(os.getenv(k, d))
        return cls(
            db_path=os.getenv("DREAM_RSI_DB", cls.db_path),
            artifact_dir=os.getenv("DREAM_RSI_ARTIFACTS", cls.artifact_dir),
            workers=integer("DREAM_RSI_WORKERS", cls.workers),
            online_rounds=integer("DREAM_RSI_ONLINE_ROUNDS", cls.online_rounds),
            replay_rounds=integer("DREAM_RSI_REPLAY_ROUNDS", cls.replay_rounds),
            beta1=number("DREAM_RSI_BETA1", cls.beta1), beta2=number("DREAM_RSI_BETA2", cls.beta2),
            execution_timeout_s=number("DREAM_RSI_TIMEOUT", cls.execution_timeout_s),
            provider=os.getenv("DREAM_RSI_PROVIDER", cls.provider),
        )
