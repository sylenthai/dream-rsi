from dream_rsi.core.interfaces import CandidateResult
from dream_rsi.execution.python_sandbox import PythonSandbox
from dream_rsi.evaluators.python import PythonCodeEvaluator


def test_sandbox_executes_code():
    r = PythonSandbox(timeout_s=5).run("print(2 + 3)")
    assert r.returncode == 0
    assert r.stdout.strip() == "5"


def test_evaluator_rejects_syntax_error():
    r = PythonCodeEvaluator().evaluate(CandidateResult(0, True, {"artifact": {"solution": "if"}}))
    assert not r.success


def test_evaluator_scores_successful_program():
    r = PythonCodeEvaluator().evaluate(CandidateResult(0, True, {"artifact": {"solution": "print('ok')"}}))
    assert r.success
    assert r.score > 0
