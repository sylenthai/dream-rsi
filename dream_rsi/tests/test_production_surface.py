from pathlib import Path
import tomllib
import pytest


def test_release_manifest_is_clean():
    root = Path(__file__).parents[2]
    bad = [p for p in root.rglob('*') if p.is_file() and p.suffix == '.tmp']
    assert not bad, bad


def test_version_is_single_source_consistent():
    root = Path(__file__).parents[2]
    data = tomllib.loads((root / 'pyproject.toml').read_text())
    version = data['project']['version']
    ns = {}
    exec((root / 'dream_rsi' / '__init__.py').read_text(), ns)
    assert ns['__version__'] == version


def test_experiment_service_contract():
    from dream_rsi.service.experiments import ExperimentService
    svc = ExperimentService()
    record = svc.submit('smoke', {'seed': 1})
    assert record.status == 'queued'
    assert svc.get(record.id).task == 'smoke'


def test_api_contract_if_installed():
    try:
        from fastapi.testclient import TestClient
        from dream_rsi.api.app import create_app
    except ImportError:
        pytest.skip('API extra is not installed in this environment')
    client = TestClient(create_app())
    assert client.get('/healthz').status_code == 200
    response = client.post('/v1/experiments', json={'task': 'smoke', 'config': {'seed': 1}})
    assert response.status_code == 202
    run_id = response.json()['id']
    assert client.get(f'/v1/experiments/{run_id}').status_code == 200


def test_api_bearer_auth_and_metrics_protection(monkeypatch):
    try:
        from fastapi.testclient import TestClient
        from dream_rsi.api.app import create_app
    except ImportError:
        pytest.skip('API extra is not installed in this environment')
    monkeypatch.setenv("DREAM_RSI_API_KEY", "super-secret-key")
    monkeypatch.setenv("DREAM_RSI_ENV", "production")
    client = TestClient(create_app())
    assert client.get('/metrics').status_code == 401
    headers = {"Authorization": "Bearer super-secret-key"}
    assert client.get('/metrics', headers=headers).status_code == 200

