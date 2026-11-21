from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


class SafetyViolation(RuntimeError):
    """Raised when an autonomous code modification violates safety guardrails."""
    pass


@dataclass(frozen=True)
class SafetyConfig:
    max_lines_per_patch: int = 250
    allow_eval: bool = False
    forbidden_modules: tuple[str, ...] = ("ctypes", "winreg", "_thread")
    protected_files: tuple[str, ...] = (
        "pyproject.toml",
        "RELEASE.md",
        "dream_rsi/execution/policy.py",
        "dream_rsi/execution/docker_sandbox.py",
        "dream_rsi/execution/python_sandbox.py",
        "dream_rsi/execution/secure.py",
        "dream_rsi/security/subprocess.py",
        "dream_rsi/evolution/safety.py",
        "dream_rsi/evolution/engine.py",
        "dream_rsi/policies/registry.py",
    )


class SafetyGatekeeper:
    """Supervisory guardrail ensuring autonomous code changes remain safe and bounded."""

    def __init__(self, config: SafetyConfig | None = None):
        self.config = config or SafetyConfig()

    def inspect_patch(self, file_path: str, new_content: str) -> None:
        """Inspect a proposed file patch for safety violations."""
        raw_replaced = file_path.replace("\\", "/").strip()
        parts = [p for p in raw_replaced.split("/") if p]
        if not raw_replaced or raw_replaced.startswith("/") or ":" in raw_replaced or ".." in parts:
            raise SafetyViolation(f"Invalid or path-traversal target '{file_path}' is strictly prohibited.")
        normalized_path = "/".join(parts)

        # Check protected files
        if any(
            normalized_path == prot
            or normalized_path.endswith("/" + prot)
            or normalized_path.endswith(prot)
            for prot in self.config.protected_files
        ):
            raise SafetyViolation(f"Modification of protected infrastructure file is denied: {file_path}")

        # Check patch size
        lines = new_content.splitlines()
        if len(lines) > self.config.max_lines_per_patch:
            raise SafetyViolation(
                f"Patch for {file_path} exceeds maximum safety budget of {self.config.max_lines_per_patch} lines (got {len(lines)})"
            )

        # Syntax check via AST
        try:
            tree = ast.parse(new_content, filename=file_path)
        except SyntaxError as exc:
            raise SafetyViolation(f"Proposed patch has syntax error: {exc}") from exc

        # Security AST rules
        for node in ast.walk(tree):
            # Check forbidden imports (exact match or root package)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    if alias.name in self.config.forbidden_modules or root_mod in self.config.forbidden_modules:
                        raise SafetyViolation(f"Forbidden module import detected: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_mod = node.module.split(".")[0]
                    if node.module in self.config.forbidden_modules or root_mod in self.config.forbidden_modules:
                        raise SafetyViolation(f"Forbidden module import detected: {node.module}")

            # Check unauthorized eval / exec / compile / __import__ calls
            if not self.config.allow_eval:
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in {"eval", "exec", "compile", "__import__"} and not normalized_path.endswith("policies/llm_developer.py"):
                        raise SafetyViolation(f"Direct call to forbidden built-in '{node.func.id}' in {file_path}")
