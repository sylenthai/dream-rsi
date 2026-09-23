from __future__ import annotations
import argparse
from ..llm.factory import create_llm
from ..research.real_experiment import run_real_experiment, save_real_experiment
from ..research.task_registry import default_coding_registry

def main() -> None:
    p=argparse.ArgumentParser(description="Dream-RSI real coding research experiment")
    p.add_argument("--provider", choices=["ollama","openai","openai-compatible","gemini"], default="ollama")
    p.add_argument("--model", default=None)
    p.add_argument("--split", default="test")
    p.add_argument("--tag", default=None)
    p.add_argument("--iterations", type=int, default=3)
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--output", default="dream-rsi-real-experiment.json")
    a=p.parse_args()
    llm=create_llm(a.provider, model=a.model)
    tasks=default_coding_registry().select(split=a.split, tag=a.tag)
    if not tasks: raise SystemExit("no benchmark tasks matched")
    report=run_real_experiment(llm, tasks, iterations=a.iterations, workers=a.workers)
    save_real_experiment(a.output, report)
    print(a.output)
