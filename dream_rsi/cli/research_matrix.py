from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..llm.factory import create_llm
from ..research.full_rsi import run_full_rsi
from ..research.multi_model import MultiModelResearchRunner
from ..research.task_registry import default_coding_registry


def main() -> None:
    parser = argparse.ArgumentParser(description="Dream-RSI reproducible multi-model research matrix")
    parser.add_argument("--provider", choices=["ollama", "openai", "openai-compatible", "gemini"], default="ollama")
    parser.add_argument("--models", required=True, help="Comma-separated model names")
    parser.add_argument("--tasks", default="sum-two,max-list", help="Comma-separated benchmark task names")
    parser.add_argument("--seeds", default="0,1", help="Comma-separated integer seeds")
    parser.add_argument("--iterations", type=int, default=2)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--output", default="artifacts/research-matrix.json")
    args = parser.parse_args()

    models = tuple(x.strip() for x in args.models.split(",") if x.strip())
    task_names = tuple(x.strip() for x in args.tasks.split(",") if x.strip())
    seeds = tuple(int(x.strip()) for x in args.seeds.split(",") if x.strip())
    if not models or not task_names or not seeds:
        raise SystemExit("models, tasks and seeds must be non-empty")
    if args.iterations < 1 or args.workers < 1:
        raise SystemExit("iterations and workers must be >= 1")

    registry = default_coding_registry()
    tasks = {task.task.name: task for task in registry.select()}
    missing = sorted(set(task_names) - set(tasks))
    if missing:
        raise SystemExit(f"unknown tasks: {', '.join(missing)}")

    def experiment(model: str, task_name: str, seed: int):
        llm = create_llm(args.provider, model=model)
        result = run_full_rsi(
            llm, tasks[task_name].task, tasks[task_name].tests,
            iterations=args.iterations, workers=args.workers,
            fresh_rounds=2, fresh_samples=1,
        )
        return {"score": result.best_fresh_score, "elapsed_s": result.elapsed_s, "seed": seed}

    report = MultiModelResearchRunner(experiment).run(models, task_names, seeds)
    payload = {"provider": args.provider, "models": list(models), "tasks": list(task_names),
               "seeds": list(seeds), "iterations": args.iterations, "workers": args.workers,
               "report": {"trials": report.trials, "aggregates": report.aggregates,
                          "pairwise_deltas": report.pairwise_deltas}}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
