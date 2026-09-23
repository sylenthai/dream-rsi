import json
from dream_rsi.llm.client import LLMResponse
from dream_rsi.research.memory import ResearchMemoryStore
from dream_rsi.research.researcher import LLMResearcher
from dream_rsi.research.orchestrator import ResearchOrchestrator

class FakeLLM:
    model = "fake"
    def __init__(self): self.calls = []
    def generate(self, messages, **kwargs):
        self.calls.append(messages)
        user = json.loads(messages[-1]["content"])
        if "available_tasks" in user:
            value = {"tasks": [user["available_tasks"][0]], "methods": [user["methods"][0]], "seeds": [user["seeds"][0]], "repetitions": 1}
        else:
            value = {"id":"h-001","question":"Does method A improve score?","rationale":"Compare controlled runs.","expected_effect":"positive","metrics":["final_score"],"constraints":["same seeds"]}
        return LLMResponse(json.dumps(value), self.model)

def test_researcher_generates_and_validates_plan(tmp_path):
    memory = ResearchMemoryStore(tmp_path / "memory.sqlite3")
    r = LLMResearcher(FakeLLM(), memory)
    h = r.propose({"baseline": 0.5})
    p = r.plan(h, ["task-a", "task-b"], ["dream-rsi", "static"], [1,2])
    assert h.id == "h-001"
    assert p.tasks == ("task-a",)
    assert len(memory.recent()) == 2

def test_orchestrator_records_failures_and_results(tmp_path):
    memory = ResearchMemoryStore(tmp_path / "memory.sqlite3")
    def runner(task, method, seed):
        if seed == 2: raise RuntimeError("boom")
        return {"score": 0.9}
    from dream_rsi.research.researcher import Hypothesis, ExperimentPlan
    h = Hypothesis("h", "q", "r", "e", ("score",))
    p = ExperimentPlan("h", "test", ("task",), ("method",), (1,2))
    out = ResearchOrchestrator(runner, memory).run(h,p)
    assert out.experiments == 2 and out.succeeded == 1 and out.failed == 1
    assert memory.recent( "research_result", 1)[0].value["failed"] == 1
