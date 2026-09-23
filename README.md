# Dream-RSI 3.3.1

Dream-RSI is a bounded research platform for replay-based recursive exploration-policy improvement, autonomous experiment planning, coding-task evaluation, repository repair, persistent research memory, and reproducible multi-model experiments.

## What is included

- Discovery Tree and replay-based research loop
- Independent fresh-world validation
- Structured LLM policy/research planning with JSON contracts
- Ollama, OpenAI-compatible, and Gemini providers
- Parallel experiment orchestration with deterministic result ordering
- Repeated-seed and multi-model research matrices
- Statistical aggregation and paired score deltas
- Failure diagnosis and bounded strategy mutation
- Failure-driven benchmark task generation
- Persistent SQLite research memory
- Repository-level patching, diagnostics, and repair
- Docker-first execution boundary with explicit resource/security policy
- Production FastAPI API with API-key authentication
- Redis Streams queue with retries, stale-message reclamation, and DLQ
- PostgreSQL or SQLite persistence
- Kubernetes and Helm deployment manifests
- Health/readiness endpoints and Prometheus metrics
- Atomic autonomous-run checkpoints
- Automated regression suite

## Release status

This archive is a **single clean release: 3.3.1**. Historical versioned implementation files and runtime database artifacts are intentionally excluded from the release archive.

The project is production-oriented, but high-assurance execution of hostile model-generated code still requires an external microVM/gVisor worker boundary. The application does not pretend that an in-process integration stub is a security boundary.

## Quick start

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1

python -m pip install -e '.[dev]'
python -m pytest -q
python -m dream_rsi.cli.run_demo
```

## LLM coding research

Local Ollama:

```bash
python -m pip install -e '.[dev]'
python -m dream_rsi.cli.llm_coding \
  --provider ollama \
  --model qwen3.5:9b \
  --name addition \
  --prompt "Read two integers from stdin and print their sum." \
  --case "2 3" "5" \
  --case "10 7" "17" \
  --iterations 5 \
  --output artifacts/llm-addition.json
```

Remote providers require their corresponding credentials in the environment.

## Autonomous research

```bash
dream-rsi-autonomous \
  --provider ollama \
  --model qwen3.5:9b \
  --task sum-two \
  --cycles 3 \
  --memory artifacts/research.sqlite3 \
  --output artifacts/autonomous-report.json
```

The autonomous loop is bounded by an explicit cycle count and does not recursively execute unrestricted LLM output.

## Multi-model research matrix

The matrix CLI is fully executable rather than a placeholder:

```bash
dream-rsi-research-matrix \
  --provider ollama \
  --models qwen3.5:9b,qwen3.5:9b \
  --tasks sum-two,max-list \
  --seeds 0,1 \
  --iterations 2 \
  --workers 2 \
  --output artifacts/research-matrix.json
```

Use distinct model names in `--models` when comparing providers/models. The output contains trials, descriptive aggregates, and paired score deltas; it does not embed a model ranking.

## Production deployment

```bash
cp .env.example .env
# Set strong, unique values for every production secret.
docker compose -f docker-compose.production.yml up --build -d
```

Production mode requires API authentication and disables local execution fallback by default. Generated/untrusted code must run in the Docker boundary; for high-assurance deployments use a separately deployed gVisor/Firecracker worker.

## Security model

The default execution policy denies network access, uses a read-only root filesystem, drops Linux capabilities, enables `no-new-privileges`, and limits CPU, memory, PID count, runtime, and output. Local subprocess fallback is development-only and is automatically disabled when `DREAM_RSI_ENV=production` unless an operator explicitly overrides it.

The Firecracker integration is deliberately an RPC boundary, not a fake in-process VM. A production high-assurance deployment should place privileged microVM lifecycle management in a separate worker/service.

## Testing and release verification

```bash
make test
make check-release
python -m compileall -q dream_rsi
```

A release is considered clean only when tests, compilation, CLI import/smoke checks, version consistency, and archive hygiene all pass.

## Research interpretation

The bundled toy and coding benchmarks validate the framework and experimental protocol. They are not evidence of general intelligence, AGI, or superiority on real-world software engineering benchmarks. Real task adapters and independently held-out evaluation environments should be supplied for substantive research claims.
