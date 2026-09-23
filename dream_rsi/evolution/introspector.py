from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FunctionSummary:
    name: str
    args: tuple[str, ...]
    docstring: str | None
    is_async: bool
    line_number: int


@dataclass(frozen=True)
class ClassSummary:
    name: str
    bases: tuple[str, ...]
    methods: tuple[str, ...]
    docstring: str | None
    line_number: int


@dataclass(frozen=True)
class ModuleSummary:
    relative_path: str
    imports: tuple[str, ...]
    classes: tuple[ClassSummary, ...]
    functions: tuple[FunctionSummary, ...]
    total_lines: int
    docstring: str | None
    complexity_score: int


@dataclass(frozen=True)
class CodebaseMap:
    root_path: str
    total_modules: int
    total_lines: int
    total_classes: int
    total_functions: int
    modules: tuple[ModuleSummary, ...]

    def manifest(self) -> dict[str, Any]:
        return asdict(self)

    def compact_summary(self, max_modules: int = 50) -> str:
        """Generate a concise textual representation suitable for LLM reasoning."""
        lines = [
            f"Codebase Overview ({self.total_modules} modules, {self.total_lines} total lines):",
            f"Classes: {self.total_classes}, Functions: {self.total_functions}",
            "---",
        ]
        for m in self.modules[:max_modules]:
            classes_str = ", ".join(c.name for c in m.classes) or "None"
            funcs_str = ", ".join(f.name for f in m.functions) or "None"
            lines.append(
                f"- Module: {m.relative_path} ({m.total_lines} lines, complexity={m.complexity_score})\n"
                f"  Classes: {classes_str}\n"
                f"  Functions: {funcs_str}"
            )
        return "\n".join(lines)


class CodebaseIntrospector:
    """Recursively reads and parses Python ASTs across the codebase."""

    def __init__(self, root: str | Path | None = None):
        if root is None:
            # Default to dream_rsi root
            root = Path(__file__).resolve().parent.parent
        self.root = Path(root).resolve()

    def scan(self, exclude_patterns: tuple[str, ...] = ("__pycache__", ".git", "runs", "dist", "artifacts")) -> CodebaseMap:
        modules: list[ModuleSummary] = []
        total_classes = 0
        total_functions = 0
        total_lines = 0

        for path in sorted(self.root.rglob("*.py")):
            if any(pat in path.parts for pat in exclude_patterns):
                continue
            try:
                rel_path = str(path.relative_to(self.root)).replace("\\", "/")
                content = path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(content, filename=str(path))
            except Exception:
                continue

            lines = len(content.splitlines())
            total_lines += lines

            docstring = ast.get_docstring(tree)
            imports: list[str] = []
            classes: list[ClassSummary] = []
            functions: list[FunctionSummary] = []
            complexity = 0

            for node in ast.walk(tree):
                # Measure structural complexity indicators
                if isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.ExceptHandler)):
                    complexity += 1
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        imports.extend(alias.name for alias in node.names)
                    elif node.module:
                        imports.append(node.module)

            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    bases = tuple(ast.unparse(b) for b in node.bases) if hasattr(ast, "unparse") else tuple(getattr(b, "id", "") for b in node.bases)
                    methods = tuple(n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
                    classes.append(ClassSummary(node.name, bases, methods, ast.get_docstring(node), node.lineno))
                    total_classes += 1
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = tuple(a.arg for a in node.args.args)
                    functions.append(FunctionSummary(node.name, args, ast.get_docstring(node), isinstance(node, ast.AsyncFunctionDef), node.lineno))
                    total_functions += 1

            modules.append(ModuleSummary(
                relative_path=rel_path,
                imports=tuple(dict.fromkeys(imports)),
                classes=tuple(classes),
                functions=tuple(functions),
                total_lines=lines,
                docstring=docstring,
                complexity_score=complexity,
            ))

        return CodebaseMap(
            root_path=str(self.root),
            total_modules=len(modules),
            total_lines=total_lines,
            total_classes=total_classes,
            total_functions=total_functions,
            modules=tuple(modules),
        )
