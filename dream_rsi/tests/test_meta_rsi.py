import json
from pathlib import Path
from dream_rsi.cli.meta_rsi import MockMetaLLM, main as cli_main
from dream_rsi.research.memory import ResearchMemoryStore
from dream_rsi.research.meta_rsi import MetaRSIController


def test_meta_rsi_controller_runs_generations(tmp_path):
    memory_path = tmp_path / "meta_memory.sqlite3"
    store = ResearchMemoryStore(memory_path)
    llm = MockMetaLLM()
    controller = MetaRSIController(llm, memory=store, min_improvement_delta=0.0)

    report = controller.run(generations=2)

    assert report.generations_completed == 2
    assert len(report.generations) == 2
    assert report.final_score >= report.initial_score
    assert len(report.accepted_policies) >= 1
    assert report.active_policy_name != ""

    # Verify persistent memory records
    recent_records = store.recent(limit=10)
    keys = {r.key for r in recent_records}
    assert "meta_rsi_run" in keys
    assert "meta_rsi_generation" in keys
    store.close()


def test_meta_rsi_cli_mock_run(tmp_path):
    memory_path = tmp_path / "cli_meta_memory.sqlite3"
    output_path = tmp_path / "meta-report.json"

    cli_main([
        "--generations", "2",
        "--memory", str(memory_path),
        "--output", str(output_path),
        "--mock",
    ])

    assert output_path.exists()
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["generations_completed"] == 2
    assert "generations" in data
    assert "cumulative_gain" in data
