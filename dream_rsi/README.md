# Dream-RSI 3.3.1

Dream-RSI is a bounded research and autonomous experimentation framework.

## Core capabilities

- replay-based exploration-policy improvement
- independent fresh-world validation
- LLM-backed policy and research planning
- coding-task evaluation
- repository repair in disposable workspaces
- failure diagnosis and bounded strategy mutation
- persistent research memory
- reproducible repeated-seed and multi-model experiments
- Docker-first execution isolation
- FastAPI + PostgreSQL + Redis production service
- Kubernetes and Helm deployment

## Safety boundary

Model output is treated as data and structured proposals. The controller does not directly execute arbitrary LLM output. Generated code is validated and routed through the configured execution boundary. In production, local subprocess fallback is disabled by default.

## Development

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
python -m dream_rsi.cli.run_demo
```

## Production

Use `docker-compose.production.yml`, Kubernetes, or Helm with external secrets. For hostile workloads requiring a high-assurance boundary, deploy a dedicated gVisor/Firecracker worker instead of relying on the application process.
