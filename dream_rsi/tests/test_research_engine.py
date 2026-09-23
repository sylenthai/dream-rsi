from dream_rsi.research.orchestrator import ResearchOrchestrator
from dream_rsi.research.researcher import Hypothesis, ExperimentPlan
from dream_rsi.research.decision import ResearchDecisionEngine

def test_parallel_matrix_and_aggregation():
    calls = []
    def runner(task, method, seed):
        calls.append((task, method, seed))
        return {"score": seed / 10}
    h = Hypothesis("h", "q", "r", "e", ("score",))
    p = ExperimentPlan("h", "test", ("a", "b"), ("m",), (1,2), repetitions=2)
    out = ResearchOrchestrator(runner, max_workers=4).run(h, p)
    assert out.experiments == 8
    assert out.succeeded == 8
    assert out.aggregates[0].count == 8
    assert round(out.aggregates[0].mean, 3) == .15
    assert len(calls) == 8

def test_decision_engine_is_conservative():
    h = Hypothesis("h", "q", "r", "e", ("score",))
    p = ExperimentPlan("h", "test", ("a",), ("m",), (1,))
    out = ResearchOrchestrator(lambda *_: {"score": 1.0}).run(h,p)
    d = ResearchDecisionEngine().decide(out)
    assert d.action == "propose_next_hypothesis"
