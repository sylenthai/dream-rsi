from __future__ import annotations

import os
import subprocess
import sys
import threading
import pytest

from dream_rsi.evolution.engine import AutonomousEvolutionEngine
from dream_rsi.evolution.safety import SafetyConfig, SafetyGatekeeper, SafetyViolation
from dream_rsi.execution.python_sandbox import PythonSandbox
from dream_rsi.llm.client import extract_json
from dream_rsi.llm.factory import create_llm
from dream_rsi.llm.providers import AnthropicClient, OpenAICompatibleClient
from dream_rsi.storage.sqlite import RunStore


def test_safety_gatekeeper_blocks_traversal_and_self_modification():
    gate = SafetyGatekeeper(SafetyConfig(max_lines_per_patch=100))

    # Path traversal and absolute paths
    for bad_path in ("../outside.py", "dream_rsi/../../escape.py", "/etc/passwd", "C:/Windows/win.ini"):
        with pytest.raises(SafetyViolation, match="path-traversal"):
            gate.inspect_patch(bad_path, "x = 1\n")

    # Protected security and self-evolution infrastructure
    for protected in (
        "dream_rsi/evolution/safety.py",
        "dream_rsi/evolution/engine.py",
        "dream_rsi/execution/docker_sandbox.py",
        "dream_rsi/execution/secure.py",
    ):
        with pytest.raises(SafetyViolation, match="protected infrastructure file"):
            gate.inspect_patch(protected, "x = 1\n")

    # Submodule imports of forbidden packages
    with pytest.raises(SafetyViolation, match="Forbidden module import"):
        gate.inspect_patch("dream_rsi/research/helper.py", "import ctypes.util\n")
    with pytest.raises(SafetyViolation, match="Forbidden module import"):
        gate.inspect_patch("dream_rsi/research/helper.py", "from ctypes.util import find_library\n")

    # Dangerous dynamic execution built-ins
    for call in ("exec('pass')", "compile('pass', 'x', 'exec')", "__import__('os')"):
        with pytest.raises(SafetyViolation, match="forbidden built-in"):
            gate.inspect_patch("dream_rsi/research/helper.py", f"{call}\n")


def test_evolution_engine_resolve_within_rejects_escape(tmp_path):
    with pytest.raises(ValueError, match="outside repository root"):
        AutonomousEvolutionEngine._resolve_within(tmp_path, "../escape.py")
    inside = AutonomousEvolutionEngine._resolve_within(tmp_path, "dream_rsi/research/ok.py")
    assert tmp_path.resolve() in inside.parents


def test_python_sandbox_isolates_environment_and_uses_isolated_python(monkeypatch):
    monkeypatch.setenv("DREAM_RSI_SECRET_TEST_TOKEN", "topsecret-do-not-leak")
    sandbox = PythonSandbox(timeout_s=5.0)
    code = (
        "import os, sys\n"
        "print('TOKEN=' + str(os.environ.get('DREAM_RSI_SECRET_TEST_TOKEN')))\n"
        "print('ISOLATED=' + str(sys.flags.isolated))\n"
    )
    res = sandbox.run(code)
    assert res.returncode == 0, res.stderr
    assert "TOKEN=None" in res.stdout
    assert "topsecret-do-not-leak" not in res.stdout
    assert "ISOLATED=1" in res.stdout


def test_extract_json_handles_thinking_tags_and_prose():
    thinking_payload = "<think>\nLet me analyze the policy delta carefully.\n</think>\nSure! Here is the JSON:\n```json\n{\"name\": \"explore\", \"beta\": 0.42}\n```\nHope this helps."
    parsed = extract_json(thinking_payload)
    assert parsed == {"name": "explore", "beta": 0.42}

    inline_prose = "Output follows -> {\"steps\": [1, 2, 3], \"ok\": true} (done)"
    parsed2 = extract_json(inline_prose)
    assert parsed2 == {"steps": [1, 2, 3], "ok": True}


def test_create_llm_supports_deepseek_groq_openrouter_and_anthropic(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test-key")
    ds = create_llm("deepseek")
    assert isinstance(ds, OpenAICompatibleClient)
    assert ds.base_url == "https://api.deepseek.com/v1"
    assert ds.model == "deepseek-chat"

    monkeypatch.setenv("GROQ_API_KEY", "gq-test-key")
    gq = create_llm("groq")
    assert isinstance(gq, OpenAICompatibleClient)
    assert gq.base_url == "https://api.groq.com/openai/v1"

    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-key")
    or_client = create_llm("openrouter")
    assert isinstance(or_client, OpenAICompatibleClient)
    assert or_client.base_url == "https://openrouter.ai/api/v1"

    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-test-key")
    ant = create_llm("anthropic")
    assert isinstance(ant, AnthropicClient)
    assert ant.base_url == "https://api.anthropic.com"

    captured = {}

    def fake_post(url, payload, headers, timeout, retries):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        return {
            "content": [{"type": "text", "text": "{\"ok\": true}"}],
            "usage": {"input_tokens": 11, "output_tokens": 7},
        }

    monkeypatch.setattr("dream_rsi.llm.providers._post", fake_post)
    resp = ant.generate([
        {"role": "system", "content": "Return JSON only."},
        {"role": "user", "content": "ping"},
    ])
    assert resp.text == '{"ok": true}'
    assert resp.input_tokens == 11
    assert resp.output_tokens == 7
    assert captured["headers"]["x-api-key"] == "ant-test-key"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["payload"]["system"] == "Return JSON only."


def test_importing_api_app_does_not_create_runs_dir(tmp_path):
    pytest.importorskip("fastapi")
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    env = dict(os.environ)
    env["PYTHONPATH"] = repo_root
    subprocess.run(
        [sys.executable, "-c", "import dream_rsi.api.app"],
        cwd=tmp_path,
        env=env,
        check=True,
    )
    assert not (tmp_path / "runs").exists()


def test_sqlite_run_store_thread_safe_reads_and_writes(tmp_path):
    store = RunStore(str(tmp_path / "concurrent.sqlite3"))
    store.create_run("r-1", "smoke", {"seed": 1})
    errors = []

    def reader():
        try:
            for _ in range(25):
                store.healthcheck()
                data = store.get_run("r-1")
                assert data is not None and data["id"] == "r-1"
                store.stale_runs(0.0)
        except Exception as exc:  # pragma: no cover - assertion target
            errors.append(exc)

    def writer():
        try:
            for idx in range(25):
                store.update_run("r-1", "running", attempts=idx + 1)
        except Exception as exc:  # pragma: no cover - assertion target
            errors.append(exc)

    threads = [threading.Thread(target=reader), threading.Thread(target=writer)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    store.close()
    assert not errors
