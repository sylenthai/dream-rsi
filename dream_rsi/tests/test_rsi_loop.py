from dream_rsi.adapters.toy import ToyDiscoveryAgent
from dream_rsi.core.loop import DreamRSI
from dream_rsi.policies.heuristic import ConservativePolicy
from dream_rsi.policies.mutator import PolicyMutator
from dream_rsi.research.fresh_validation import FreshValidator


def test_fresh_gate_rejects_regression():
    current=ConservativePolicy(.35)
    engine=DreamRSI(ToyDiscoveryAgent(),PolicyMutator(),current,fresh_validator=FreshValidator(ToyDiscoveryAgent(),workers=2,rounds=2),online_rounds=2,replay_rounds=4,min_fresh_delta=0.0)
    report=engine.run_iteration(1)
    assert report.selected_policy == current.name
    assert report.fresh_validation

class _Resp:
    def __init__(self, text): self.text=text
class _MockLLM:
    def generate(self, messages, **kwargs):
        return _Resp('{"name":"generated_width","source":"class GeneratedPolicy(PrefixPolicy):\\n    def reset(self):\\n        self.calls = 0\\n    def select_batch(self, view, max_parallelism):\\n        self.calls += 1\\n        return view.eligible()[:max_parallelism]","rationale":"increase breadth"}')

def test_llm_policy_developer_builds_valid_policy():
    from dream_rsi.policies.llm_developer import LLMPolicyDeveloper
    from dream_rsi.policies.registry import PolicyRegistry
    p=LLMPolicyDeveloper(_MockLLM(),PolicyRegistry()).propose(ConservativePolicy(),[{"avg_reward":1.0}])
    assert p.name == 'generated_width'
    p.reset()
    assert p.select_batch(type('V',(),{'eligible':lambda self:['root','n1']})(),2)==['root','n1']
