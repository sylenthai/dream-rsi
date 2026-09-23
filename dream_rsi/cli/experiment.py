from __future__ import annotations
import argparse, json
from ..research.experiment import run_trials, summarize, compare, save_report, save_csv
from ..research.tasks import default_task_suite, get_split


def main():
    ap = argparse.ArgumentParser(description="Dream-RSI held-out repeated-seed research benchmark")
    ap.add_argument("--methods", nargs="+", default=["dream-rsi", "no-fresh-gate", "replay-only", "static", "random"])
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--iterations", type=int, default=5)
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--split", choices=["train", "validation", "test", "held-out"], default="test")
    ap.add_argument("--output", default="artifacts/experiment.json")
    args = ap.parse_args()
    seeds = list(range(args.seeds))
    suite = default_task_suite()
    tasks = get_split(suite, args.split)
    results = run_trials(args.methods, seeds, args.iterations, args.workers, args.rounds, args.split, tasks)
    summaries = summarize(results)
    base = "dream-rsi"
    comparisons = [compare(results, base, m) for m in args.methods if m != base]
    protocol = {
        "seed_policy": "same seeds paired within task",
        "primary_metric": "independent fresh-world best score",
        "diagnostic_metric": "final replay score",
        "task_split": args.split,
        "task_ids": [t.task_id for t in tasks],
        "methods": args.methods,
        "iterations": args.iterations,
        "rounds": args.rounds,
        "workers": args.workers,
        "note": "TaskAwareToyAgent is a synthetic benchmark adapter, not a real-world LLM benchmark.",
    }
    save_report(args.output, results, summaries, comparisons, protocol=protocol)
    save_csv(args.output.rsplit(".", 1)[0] + ".csv", results)
    print(json.dumps({"summaries": [x.to_dict() for x in summaries], "comparisons": comparisons}, indent=2))

if __name__ == "__main__":
    main()
