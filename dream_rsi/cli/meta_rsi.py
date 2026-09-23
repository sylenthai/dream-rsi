from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..llm.client import LLMResponse
from ..llm.factory import create_llm
from ..research.memory import ResearchMemoryStore
from ..research.meta_rsi import MetaRSIController


class MockMetaLLM:
    """Mock LLM that generates valid dynamic exploration policies and tasks."""
    model = "mock-meta-llm"

    def generate(self, messages, **kwargs):
        content = messages[-1].get("content", "")
        # If it's asking for a task (requirements keyword present)
        if "new_task_name" in content or "benchmark designer" in str(messages[0].get("content", "")):
            task_json = json.dumps({
                "new_task_name": "meta-task-synthetic",
                "prompt": "Read numbers and print maximum",
                "tests": [{"stdin": "1 5 3", "expected_stdout": "5\n", "name": "case1"}],
                "rationale": "Generated harder benchmark edge-case",
                "difficulty": "hard",
                "tags": ["algorithm", "curriculum"],
            })
            return LLMResponse(task_json, self.model)

        # Policy generation
        policy_code = (
            "class DynamicSynthesizedPolicy(PrefixPolicy):\n"
            "    name = 'dynamic_meta_policy'\n"
            "    def reset(self):\n"
            "        pass\n"
            "    def select_batch(self, view, max_parallelism):\n"
            "        eligible = view.eligible()\n"
            "        return eligible[:min(max_parallelism, len(eligible))]\n"
        )
        policy_json = json.dumps({
            "name": "dynamic_meta_policy",
            "source": policy_code,
            "rationale": "Prioritize all eligible frontier nodes evenly with breadth",
        })
        return LLMResponse(policy_json, self.model)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Dream-RSI: Recursive Self-Improvement (Meta-RSI) Loop")
    p.add_argument("--generations", type=int, default=3, help="Number of self-improvement generations")
    p.add_argument("--provider", choices=["ollama", "openai", "openai-compatible", "gemini"], default="ollama")
    p.add_argument("--model", default=None, help="LLM model name")
    p.add_argument("--memory", default="dream_rsi_memory.sqlite3", help="Persistent SQLite memory path")
    p.add_argument("--output", default="artifacts/meta-rsi-report.json", help="Path to write report JSON")
    p.add_argument("--mock", action="store_true", help="Use built-in mock LLM for testing/demo")
    args = p.parse_args(argv)

    if args.mock:
        llm = MockMetaLLM()
    else:
        llm = create_llm(args.provider, model=args.model)

    store = ResearchMemoryStore(args.memory)
    controller = MetaRSIController(llm, memory=store)
    report = controller.run(generations=args.generations)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report.manifest(), indent=2), encoding="utf-8")

    print(f"Meta-RSI completed {report.generations_completed} generations.")
    print(f"Initial score: {report.initial_score:.4f} -> Final score: {report.final_score:.4f} (Delta: {report.cumulative_gain:+.4f})")
    print(f"Active policy: {report.active_policy_name}")
    print(f"Report written to: {out_path.resolve()}")


if __name__ == "__main__":
    main()
