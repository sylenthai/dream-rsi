from dream_rsi.core.interfaces import CandidateResult
from dream_rsi.evaluators.coding import CodeTestCase, CodingTestEvaluator
from dream_rsi.execution.python_sandbox import PythonSandbox


def test_coding_evaluator_scores_all_cases():
    evaluator = CodingTestEvaluator([
        CodeTestCase("2 3\n", "5\n", "sum-1"),
        CodeTestCase("10 7\n", "17\n", "sum-2"),
    ], PythonSandbox(timeout_s=5))
    candidate = CandidateResult(0.0, True, {
        "artifact": {"solution": "a,b=map(int,input().split())\nprint(a+b)"}
    })
    result = evaluator.evaluate(candidate)
    assert result.score == 1.0
    assert result.success is True
    assert result.diagnostics["passed"] == 2


def test_coding_evaluator_rejects_imports():
    evaluator = CodingTestEvaluator([CodeTestCase("1\n", "1\n")])
    candidate = CandidateResult(0.0, True, {"artifact": {"solution": "import os\nprint(1)"}})
    result = evaluator.evaluate(candidate)
    assert result.success is False
    assert result.score == float("-inf")
