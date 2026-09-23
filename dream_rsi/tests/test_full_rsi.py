import json
from dream_rsi.agents.llm_discovery import LLMCodingDiscoveryAgent
from dream_rsi.agents.coding import CodingTask
from dream_rsi.core.tree import DiscoveryTree
from dream_rsi.core.interfaces import CandidateResult
from dream_rsi.llm.client import LLMResponse

class FakeLLM:
    model = "fake"
    def generate(self, messages, **kwargs):
        return LLMResponse('{"solution":"print(2 + 3)","explanation":"constant test"}', 0, 0)

def test_llm_discovery_agent_returns_artifact():
    agent = LLMCodingDiscoveryAgent(FakeLLM(), CodingTask("x", "print 5"))
    tree = DiscoveryTree()
    result = agent.generate("root", {"tree": tree})
    assert result.diagnostics["artifact"]["solution"] == "print(2 + 3)"
