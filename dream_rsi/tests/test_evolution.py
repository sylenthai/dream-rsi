import json
import os
from pathlib import Path
import pytest

if os.getenv("DREAM_RSI_IN_STAGING") == "1":
    pytest.skip("Skipping evolution engine inside staging sandbox", allow_module_level=True)

from dream_rsi.cli.evolve import MockArchitectLLM, main as cli_main
from dream_rsi.evolution.introspector import CodebaseIntrospector
from dream_rsi.evolution.safety import SafetyConfig, SafetyGatekeeper, SafetyViolation
from dream_rsi.evolution.architect import SelfArchitectAgent
from dream_rsi.evolution.engine import AutonomousEvolutionEngine
from dream_rsi.research.memory import ResearchMemoryStore


def test_codebase_introspector():
    introspector = CodebaseIntrospector()
    cb_map = introspector.scan()

    assert cb_map.total_modules >= 20
    assert cb_map.total_classes >= 20
    assert cb_map.total_functions >= 30
    assert cb_map.total_lines > 1000

    summary = cb_map.compact_summary(max_modules=5)
    assert "Codebase Overview" in summary
    assert "Module:" in summary


def test_safety_gatekeeper_blocks_violations():
    gate = SafetyGatekeeper(SafetyConfig(max_lines_per_patch=50))

    # 1. Block protected file
    with pytest.raises(SafetyViolation, match="protected infrastructure file"):
        gate.inspect_patch("pyproject.toml", "x = 1\n")

    # 2. Block forbidden module import
    with pytest.raises(SafetyViolation, match="Forbidden module import"):
        gate.inspect_patch("dream_rsi/some_file.py", "import ctypes\n")

    # 3. Block syntax errors
    with pytest.raises(SafetyViolation, match="syntax error"):
        gate.inspect_patch("dream_rsi/some_file.py", "def foo(:\n")

    # 4. Block oversized patches
    with pytest.raises(SafetyViolation, match="exceeds maximum safety budget"):
        gate.inspect_patch("dream_rsi/some_file.py", "\n" * 60)

    # 5. Allow safe valid code
    gate.inspect_patch("dream_rsi/research/helper.py", "def add(a: int, b: int) -> int:\n    return a + b\n")


def test_autonomous_evolution_engine(tmp_path):
    memory_path = tmp_path / "evolve_mem.sqlite3"
    store = ResearchMemoryStore(memory_path)
    llm = MockArchitectLLM()

    engine = AutonomousEvolutionEngine(llm, memory=store, auto_apply=False)
    report = engine.run(cycles=1)

    assert report.cycles_completed == 1
    assert len(report.history) == 1
    cycle_0 = report.history[0]
    assert cycle_0.safety_passed is True
    # In sandbox verification, test suite passes
    assert cycle_0.tests_passed is True
    assert cycle_0.applied is False  # auto_apply was False

    # Check memory persistence
    recent = store.recent(limit=5)
    keys = {r.key for r in recent}
    assert "evolution_run" in keys or "evolution_cycle" in keys
    store.close()


def test_evolution_cli_mock(tmp_path):
    memory_path = tmp_path / "cli_evolve_mem.sqlite3"
    out_path = tmp_path / "evolution-report.json"

    cli_main([
        "--cycles", "1",
        "--memory", str(memory_path),
        "--output", str(out_path),
        "--mock",
    ])

    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["cycles_completed"] == 1
    assert len(data["history"]) == 1
