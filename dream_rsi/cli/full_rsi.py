from __future__ import annotations
import argparse, json
from ..agents.coding import CodingTask
from ..evaluators.coding import CodeTestCase
from ..llm.factory import create_llm
from ..research.full_rsi import run_full_rsi, save_full_rsi


def main():
    ap = argparse.ArgumentParser(description="Run full LLM + Dream-RSI coding experiment")
    ap.add_argument("--provider", default="ollama", choices=["ollama", "openai", "openai-compatible", "gemini"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--name", default="full-rsi-task")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--case", action="append", nargs=2, metavar=("STDIN", "EXPECTED"), required=True)
    ap.add_argument("--iterations", type=int, default=3)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--online-rounds", type=int, default=4)
    ap.add_argument("--replay-rounds", type=int, default=20)
    ap.add_argument("--fresh-rounds", type=int, default=4)
    ap.add_argument("--fresh-samples", type=int, default=2)
    ap.add_argument("--output", default="artifacts/full-rsi.json")
    args = ap.parse_args()
    llm = create_llm(args.provider, args.model)
    task = CodingTask(args.name, args.prompt)
    tests = tuple(CodeTestCase(s, e, f"case-{i+1}") for i, (s, e) in enumerate(args.case))
    result = run_full_rsi(llm, task, tests, args.iterations, args.workers,
                          args.online_rounds, args.replay_rounds,
                          args.fresh_rounds, args.fresh_samples)
    save_full_rsi(args.output, result)
    print(json.dumps({"task": result.task, "model": result.model,
                      "iterations": result.iterations, "selected_policy": result.selected_policy,
                      "best_fresh_score": result.best_fresh_score,
                      "final_replay_score": result.final_replay_score,
                      "elapsed_s": result.elapsed_s, "output": args.output}, indent=2))


if __name__ == "__main__":
    main()
