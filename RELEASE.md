# Dream-RSI 3.3.1 Release Verification

## Release contents

This archive contains only the current 3.3.1 source tree and the matching wheel artifact.
Historical versioned test filenames, stale deployment versions, SQLite runtime state, Python bytecode, pytest caches, and temporary files are excluded.

## Verification completed

- Python test suite: **42 passed**
- Python bytecode compilation: **passed**
- Demo smoke run: **passed**
- Autonomous CLI import/help: **passed**
- Research-matrix CLI import/help: **passed**
- Source release version consistency: **3.3.1**
- Wheel build: **passed**
- Wheel installation in a clean virtual environment: **passed**
- Installed package version: **3.3.1**
- Installed `dream-rsi` CLI smoke: **passed**
- Legacy release version scan: **clean**
- Runtime/cache artifact scan: **clean**

## Production security note

Production mode disables local subprocess fallback by default. Docker is the application-level execution boundary. A high-assurance deployment for hostile code should place privileged microVM/gVisor lifecycle management in a separately deployed worker/service.

No software project can honestly guarantee the absence of every future defect. This release has been statically inspected and regression-tested against the source and runtime surfaces available in the supplied archive.
