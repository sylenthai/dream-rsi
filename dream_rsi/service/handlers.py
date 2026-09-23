from __future__ import annotations
from typing import Any

def build_handlers() -> dict[str, Any]:
    def smoke(task: str, config: dict[str, Any]) -> dict[str, Any]:
        return {"task": task, "message": "worker execution completed", "config": {k:v for k,v in config.items() if not str(k).startswith("_")}}

    def real_experiment(task: str, config: dict[str, Any]) -> dict[str, Any]:
        from ..llm.factory import create_llm
        from ..research.real_experiment import run_real_experiment
        from ..research.task_registry import default_coding_registry
        provider = config.get("provider", "ollama")
        llm = create_llm(provider, model=config.get("model"))
        tasks = default_coding_registry().select(split=config.get("split", "test"), tag=config.get("tag"))
        if not tasks: raise ValueError("no benchmark tasks matched")
        report = run_real_experiment(llm, tasks, iterations=int(config.get("iterations", 3)), workers=int(config.get("workers", 2)))
        return {"model": report.model, "tasks": report.tasks, "started_at_epoch": report.started_at_epoch, "elapsed_s": report.elapsed_s}

    return {"smoke": smoke, "real_experiment": real_experiment}
