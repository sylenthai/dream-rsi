from __future__ import annotations
import argparse, json
from ..agents.coding import CodingTask
from ..evaluators.coding import CodeTestCase
from ..llm.factory import create_llm
from ..research.llm_coding import IterativeLLMCodingHarness, save_result


def main():
    ap = argparse.ArgumentParser(description="Run a real LLM coding discovery experiment")
    ap.add_argument("--provider", default="ollama", choices=["ollama", "openai", "openai-compatible", "gemini"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--name", default="coding-task")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--case", action="append", nargs=2, metavar=("STDIN", "EXPECTED"), required=True,
                    help="repeat for each deterministic stdin/expected-output test")
    ap.add_argument("--iterations", type=int, default=5)
    ap.add_argument("--output", default="artifacts/llm-coding.json")
    args = ap.parse_args()
    llm = create_llm(args.provider, args.model)
    task = CodingTask(args.name, args.prompt)
    tests = tuple(CodeTestCase(stdin=s, expected_stdout=e, name=f"case-{i+1}") for i, (s, e) in enumerate(args.case))
    result = IterativeLLMCodingHarness(llm, task, tests).run(args.iterations)
    save_result(args.output, result)
    print(json.dumps({
        "task": result.task,
        "model": result.model,
        "iterations": result.iterations,
        "best_score": result.best_score,
        "final_score": result.final_score,
        "successful_candidates": result.successful_candidates,
        "output": args.output,
    }, indent=2))


if __name__ == "__main__":
    main()
