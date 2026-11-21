# Contributing to Dream-RSI

Thank you for your interest in contributing to **Dream-RSI**! Contributions spanning bug fixes, sandbox hardening, new task adapters, LLM providers, statistical evaluators, and documentation are warmly welcomed.

## Development Setup

```bash
git clone https://github.com/sylenthai/dream-rsi.git
cd dream-rsi

python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install -e ".[dev,api]"
```

## Verification Checklist Before Opening a PR

Run the full verification suite locally before submitting changes:

```bash
# 1. Run regression & release-integrity test suites
python -m pytest -q

# 2. Verify bytecode compilation across all packages
python -m compileall -q dream_rsi

# 3. Verify CLI smoke demo
python -m dream_rsi.cli.run_demo
```

Ensure temporary `runs/`, `artifacts/`, or `.sqlite3` files are removed before committing.

## Code & Security Guidelines

- **Type Annotations & Determinism**: Keep public dataclasses, evaluators, and CLI entrypoints typed and reproducible across seeds.
- **No Unbounded Self-Modification**: Autonomous evolution rules in `dream_rsi/evolution/safety.py` and execution policies in `dream_rsi/execution/` must fail closed.
- **No Secret Exposure**: Never commit API keys, `.env` files, or credentials; test suites must mock network calls or use isolated temporary paths (`tmp_path`).
- **Tests Required**: Add focused regression tests in `dream_rsi/tests/` for every bug fix or new feature.

## License

By submitting a pull request, you agree that your contributions will be licensed under the **Apache License 2.0** (`LICENSE`).
