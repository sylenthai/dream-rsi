from pathlib import Path
import tomllib


def test_release_version_and_artifact_consistency():
    root = Path(__file__).parents[2]
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    assert version == "3.3.1"
    namespace = {}
    exec((root / "dream_rsi" / "__init__.py").read_text(), namespace)
    assert namespace["__version__"] == version
    assert 'version: 3.3.1' in (root / "deploy/helm/dream-rsi/Chart.yaml").read_text()
    assert 'appVersion: "3.3.1"' in (root / "deploy/helm/dream-rsi/Chart.yaml").read_text()
    assert 'tag: "3.3.1"' in (root / "deploy/helm/dream-rsi/values.yaml").read_text()


def test_no_legacy_release_versions_or_runtime_artifacts():
    root = Path(__file__).parents[2]
    forbidden = tuple(".".join((x, y, z)) for x, y, z in (("1", "1", "0"), ("2", "7", "0"), ("3", "3", "0"), ("0", "7", "0")))
    allowed_suffixes = {".py", ".toml", ".yaml", ".yml", ".md", ".env", ".example", ".dockerfile"}
    for path in root.rglob("*"):
        if not path.is_file() or path.name.startswith(".") and path.name not in {".env.example"}:
            continue
        if path.suffix not in allowed_suffixes:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(value in text for value in forbidden), path
    # Runtime/cache directories are excluded from the release archive by the release check.


def test_all_cli_modules_import_cleanly():
    import importlib
    modules = [
        "dream_rsi.cli.research",
        "dream_rsi.cli.experiment",
        "dream_rsi.cli.full_rsi",
        "dream_rsi.cli.llm_coding",
        "dream_rsi.cli.real_experiment",
        "dream_rsi.cli.autonomous",
        "dream_rsi.cli.repair",
        "dream_rsi.cli.worker",
        "dream_rsi.cli.research_matrix",
        "dream_rsi.cli.run_demo",
        "dream_rsi.cli.meta_rsi",
        "dream_rsi.cli.evolve",
    ]
    for module in modules:
        importlib.import_module(module)


def test_production_executor_does_not_fallback_to_local(monkeypatch):
    monkeypatch.setenv("DREAM_RSI_ENV", "production")
    from dream_rsi.execution.secure import SecurePythonExecutor
    executor = SecurePythonExecutor(prefer_docker=False)
    assert executor.allow_local_fallback is False
    assert executor.mode == "docker-unavailable"
