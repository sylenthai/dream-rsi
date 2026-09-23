from dream_rsi.agents.coding import CodingTask
from dream_rsi.evaluators.coding import CodeTestCase
from dream_rsi.research.llm_coding import IterativeLLMCodingHarness
from dream_rsi.llm.client import LLMResponse

class MockLLM:
    model = "mock-coder"
    def generate(self, messages, **kwargs):
        code = "import os\nprint('bad')" if 'feedback' not in messages[-1]['content'] else "print('5')"
        # Always provide the correct candidate so the harness tests evaluation wiring.
        code = "print('5')"
        return LLMResponse('{"solution": "' + code.replace('\\', '\\\\').replace('"', '\\"') + '", "explanation": "test"}', self.model)

def test_iterative_llm_coding_harness():
    task = CodingTask("addition", "print 5")
    tests = (CodeTestCase("", "5\n", "basic"),)
    result = IterativeLLMCodingHarness(MockLLM(), task, tests).run(3)
    assert result.best_score == 1.0
    assert result.successful_candidates == 3
    assert result.best_solution.strip() == "print('5')"
