# Security Policy

## Supported Versions

Only the latest release on `main` is actively maintained with security fixes:

| Version | Supported |
| --- | --- |
| `3.3.1` | Yes |

## Defense-in-Depth Architecture

Dream-RSI is designed for running LLM-generated code, policy mutations, and repository patches under explicit containment rules:

1. **Container Execution Policy (`dream_rsi/execution/policy.py`, `docker_sandbox.py`, `repository/runner.py`)**:
   - Network disabled by default (`--network none`).
   - Read-only root filesystem (`--read-only`) with bounded `noexec,nosuid` `/tmp` tmpfs.
   - All Linux capabilities dropped (`--cap-drop ALL`) and `--security-opt no-new-privileges`.
   - Strict memory, CPU, PID count, timeout, and output size bounds.
   - Explicit working directory confinement (`-w /workspace`) and non-privileged permissions handling.
2. **Production Fallback Lockout (`DREAM_RSI_ENV=production`)**:
   - Local subprocess fallback (`PythonSandbox` / `RepositoryRunner`) is automatically disabled in production mode unless explicitly overridden.
   - For hostile multi-tenant workloads, delegate execution to an isolated Firecracker MicroVM or gVisor worker via `FirecrackerBackend` RPC (`dream_rsi/execution/microvm.py`).
3. **Hardened Local Development Sandbox (`dream_rsi/execution/python_sandbox.py`, `dream_rsi/security/subprocess.py`)**:
   - Invokes `sys.executable -I` (Python isolated mode) inside an ephemeral temporary directory.
   - Strips `os.environ` down to `PATH`, `PYTHONNOUSERSITE`, and `PYTHONDONTWRITEBYTECODE` so host API keys and database credentials are not leaked into candidate scripts.
4. **Autonomous Self-Evolution Guardrails (`dream_rsi/evolution/safety.py`, `engine.py`)**:
   - Blocks path traversal (`..`), absolute paths, and writes outside `repo_root`.
   - Protects core infrastructure, sandbox, security, and evolution guardrail files from autonomous modification.
   - Enforces AST checks blocking forbidden modules (including submodules) and dynamic execution calls (`eval`, `exec`, `compile`, `__import__`), plus syntax validation and per-patch line budgets.
   - Validates every candidate patch inside an isolated staging directory against the full test suite before promotion.
5. **API Authentication (`dream_rsi/api/app.py`)**:
   - Uses constant-time `hmac.compare_digest` verification for `X-API-Key` and `Authorization: Bearer` tokens, and fails closed (`503`) if `DREAM_RSI_ENV=production` lacks `DREAM_RSI_API_KEY`.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for suspected security vulnerabilities.

Instead, report vulnerabilities privately through GitHub Security Advisories:
- https://github.com/sylenthai/dream-rsi/security/advisories/new

Include steps to reproduce, affected file paths, potential impact, and any suggested mitigation. We aim to acknowledge reports within 48 hours and release verified patches promptly.
