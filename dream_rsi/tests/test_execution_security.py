import pytest

def test_execution_policy_defaults_to_deny_network():
    from dream_rsi.execution import ExecutionPolicy
    p=ExecutionPolicy()
    assert p.network is False
    assert p.read_only_root is True
    assert p.no_new_privileges is True
    assert p.drop_all_capabilities is True

def test_execution_policy_rejects_unsafe_limits():
    from dream_rsi.execution import ExecutionPolicy
    with pytest.raises(ValueError): ExecutionPolicy(pids_limit=0).validate()
    with pytest.raises(ValueError): ExecutionPolicy(timeout_s=0).validate()

def test_firecracker_is_explicit_integration_boundary():
    from dream_rsi.execution import FirecrackerBackend
    b=FirecrackerBackend()
    assert not b.configured
    with pytest.raises(RuntimeError): b.run("print(1)")

def test_docker_command_policy_without_running_docker(monkeypatch):
    from dream_rsi.execution.docker_sandbox import DockerSandbox
    d=DockerSandbox()
    monkeypatch.setattr('dream_rsi.execution.docker_sandbox.shutil.which', lambda _: None)
    r=d.run('print(1)')
    assert r.available is False and r.returncode == -127

def test_secure_python_executor_fallback_on_docker_unavailable(monkeypatch):
    from dream_rsi.execution.secure import SecurePythonExecutor
    from dream_rsi.execution.docker_sandbox import DockerExecutionResult
    executor = SecurePythonExecutor(prefer_docker=True, allow_local_fallback=True)
    monkeypatch.setattr(executor.docker, 'run', lambda *args, **kwargs: DockerExecutionResult(1, '', 'cannot connect to the docker daemon', 0.0, available=False))
    result = executor.run('print("hello")')
    assert result.returncode == 0
    assert "hello" in result.stdout

def test_firecracker_rpc_client(monkeypatch):
    import io, json
    from dream_rsi.execution.microvm import FirecrackerBackend
    backend = FirecrackerBackend(endpoint="http://microvm.local:8080")
    assert backend.configured is True

    class MockResponse:
        def __init__(self, data):
            self.data = data
        def read(self):
            return json.dumps(self.data).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=30: MockResponse({"returncode": 0, "stdout": "microvm ok", "stderr": "", "duration_s": 0.05, "timed_out": False}))
    res = backend.run("print('ok')")
    assert res.returncode == 0
    assert res.stdout == "microvm ok"
    assert res.backend == "microvm"

