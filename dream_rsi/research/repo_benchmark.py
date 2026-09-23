from __future__ import annotations
import hashlib, json, shutil, subprocess, tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

@dataclass(frozen=True)
class RepositoryTask:
    name: str
    repository: str
    prompt: str
    test_command: tuple[str, ...]
    split: str = "held-out"
    tags: tuple[str, ...] = ()

    def manifest(self) -> dict[str, Any]:
        return asdict(self)

class RepositoryTaskRunner:
    """Small repository-level benchmark adapter. It clones/copies a local repo into a temp workspace,
    applies a model-produced patch or file map, then runs the declared tests. It is intentionally not
    presented as official SWE-bench compatibility."""
    def __init__(self, timeout_s: float = 30.0):
        self.timeout_s = timeout_s
    @staticmethod
    def fingerprint(path: str | Path) -> str:
        root = Path(path); h = hashlib.sha256()
        for p in sorted(x for x in root.rglob('*') if x.is_file() and '.git' not in x.parts):
            h.update(str(p.relative_to(root)).encode()); h.update(p.read_bytes())
        return h.hexdigest()
    def run(self, task: RepositoryTask, files: dict[str, str]) -> dict[str, Any]:
        src = Path(task.repository)
        if not src.exists():
            raise FileNotFoundError(src)
        with tempfile.TemporaryDirectory(prefix="dream-rsi-repo-") as tmp:
            root = Path(tmp) / "repo"; shutil.copytree(src, root)
            for rel, content in files.items():
                target = root / rel; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(content, encoding="utf-8")
            try:
                p = subprocess.run(task.test_command, cwd=root, capture_output=True, text=True, timeout=self.timeout_s)
                return {"task": task.name, "returncode": p.returncode, "success": p.returncode == 0,
                        "stdout": p.stdout[-5000:], "stderr": p.stderr[-5000:],
                        "repository_fingerprint": self.fingerprint(root)}
            except subprocess.TimeoutExpired as exc:
                return {"task": task.name, "returncode": -1, "success": False, "timeout": True,
                        "stdout": (exc.stdout or "")[-5000:], "stderr": (exc.stderr or "")[-5000:]}
