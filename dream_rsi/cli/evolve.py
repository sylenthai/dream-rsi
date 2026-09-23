from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..evolution.engine import AutonomousEvolutionEngine
from ..llm.client import LLMResponse
from ..llm.factory import create_llm
from ..research.memory import ResearchMemoryStore


class MockArchitectLLM:
    """Mock LLM proposing a safe, self-improving heuristic optimization."""
    model = "mock-architect-llm"

    def generate(self, messages, **kwargs):
        # Generates a valid, safe improvement to a helper module
        new_helper = (
            '"""Autonomous self-improved utility module."""\n'
            'from __future__ import annotations\n\n'
            'def fast_normalize_scores(scores: list[float]) -> list[float]:\n'
            '    """Optimized vector score normalizer."""\n'
            '    if not scores:\n'
            '        return []\n'
            '    total = sum(scores)\n'
            '    if total == 0:\n'
            '        return [0.0 for _ in scores]\n'
            '    return [s / total for s in scores]\n'
        )
        proposal_json = json.dumps({
            "target_file": "dream_rsi/research/fast_math.py",
            "rationale": "Add dedicated fast vector normalization helper for research metrics",
            "expected_benefit": "Accelerates score normalization by 15%",
            "new_content": new_helper,
        })
        return LLMResponse(proposal_json, self.model)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Dream-RSI: Autonomous Supervised Codebase Self-Evolution")
    p.add_argument("--cycles", type=int, default=2, help="Number of autonomous evolution cycles")
    p.add_argument("--provider", choices=["ollama", "openai", "openai-compatible", "gemini"], default="ollama")
    p.add_argument("--model", default=None, help="LLM model name")
    p.add_argument("--memory", default="dream_rsi_memory.sqlite3", help="Persistent SQLite memory path")
    p.add_argument("--output", default="artifacts/evolution-report.json", help="Path to write report JSON")
    p.add_argument("--mock", action="store_true", help="Use built-in mock architect LLM for dry-run/demo")
    p.add_argument("--auto-apply", action="store_true", help="Atomically apply verified passing patches to codebase")
    args = p.parse_args(argv)

    if args.mock:
        llm = MockArchitectLLM()
    else:
        llm = create_llm(args.provider, model=args.model)

    store = ResearchMemoryStore(args.memory)
    engine = AutonomousEvolutionEngine(llm, memory=store, auto_apply=args.auto_apply)
    report = engine.run(cycles=args.cycles)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report.manifest(), indent=2), encoding="utf-8")

    print(f"Autonomous Evolution completed {report.cycles_completed} cycles.")
    print(f"Verified Successful: {report.successful_evolutions}, Rejected/Failed: {report.failed_evolutions}")
    for c in report.history:
        status = "PASSED" if c.tests_passed else "FAILED"
        print(f"- Cycle {c.cycle}: target={c.target_file} safety={c.safety_passed} tests={status} applied={c.applied}")
    print(f"Evolution report written to: {out_path.resolve()}")


if __name__ == "__main__":
    main()
