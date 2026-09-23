from dream_rsi.research.researcher import Hypothesis, ExperimentPlan, LLMResearcher, ResearchMutation
from dream_rsi.research.orchestrator import ResearchCycleResult
from dream_rsi.research.decision import ResearchDecision
from dream_rsi.research.self_improvement import FailureAnalyzer, SelfImprovementEngine
from dream_rsi.research.memory import ResearchMemoryStore


def result_with_failures():
    return ResearchCycleResult("h1", 4, 1, 3, 0.0, 0.1, (
        {"task_id":"a","method":"m","seed":1,"repetition":0,"status":"failed","error":"timeout"},
        {"task_id":"b","method":"m","seed":1,"repetition":0,"status":"failed","error":"timeout"},
        {"task_id":"c","method":"m","seed":1,"repetition":0,"status":"failed","error":"timeout"},
        {"task_id":"d","method":"m","seed":1,"repetition":0,"status":"succeeded","score":0.2},
    ), ())


def test_failure_analyzer_is_deterministic():
    d = FailureAnalyzer().diagnose(result_with_failures())
    assert d.category == "timeout"
    assert len(d.evidence) == 3

class FakeLLM:
    def generate(self, messages, temperature=0.2, max_tokens=1800, response_format="json"):
        class R: text='{"id":"mut-1","parent_hypothesis_id":"h1","trigger":"timeout","change":"reduce_parallelism","expected_effect":"fewer execution timeouts","constraints":[]}'
        return R()

def test_self_improvement_mutates_with_whitelist(tmp_path):
    mem = ResearchMemoryStore(tmp_path / "m.sqlite")
    researcher = LLMResearcher(FakeLLM(), mem)
    engine = SelfImprovementEngine(researcher, mem)
    h = Hypothesis("h1", "q", "r", "e", ("score",))
    decision = ResearchDecision("repair_or_replan", "too many failures", {"success_rate": .25})
    step = engine.improve(h, result_with_failures(), decision, ["reduce_parallelism", "increase_timeout"])
    assert step.action == "mutate_strategy"
    assert step.mutation.change == "reduce_parallelism"
    assert mem.recent("research_mutation", 1)[0].value["id"] == "mut-1"
