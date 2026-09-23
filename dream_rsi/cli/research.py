from __future__ import annotations

import argparse
import json
from ..config.settings import Settings
from ..storage.sqlite import RunStore
from ..research.runner import ResearchRunner
from ..adapters.toy import ToyDiscoveryAgent
from ..policies.heuristic import ConservativePolicy
from ..policies.mutator import PolicyMutator
from ..policies.llm_developer import LLMPolicyDeveloper
from ..policies.registry import PolicyRegistry
from ..research.fresh_validation import FreshValidator
from ..llm.factory import create_llm
from ..core.loop import DreamRSI


def main():
    ap = argparse.ArgumentParser(description="Dream-RSI research runner")
    ap.add_argument('--iterations', type=int, default=3)
    ap.add_argument('--task', default='toy-research')
    ap.add_argument('--policy-provider', choices=['toy', 'ollama', 'openai', 'openai-compatible', 'gemini'], default='toy')
    ap.add_argument('--model', default=None)
    args = ap.parse_args()
    s = Settings.from_env()
    store = RunStore(s.db_path)
    if args.policy_provider == 'toy':
        developer = PolicyMutator()
    else:
        developer = LLMPolicyDeveloper(create_llm(args.policy_provider, args.model), PolicyRegistry())
    validator = FreshValidator(ToyDiscoveryAgent(seed=s.random_seed + 1000), workers=s.workers,
                               rounds=max(1, s.fresh_validation_rounds))
    engine = DreamRSI(
        ToyDiscoveryAgent(seed=s.random_seed), developer, ConservativePolicy(),
        fresh_validator=validator, workers=s.workers, online_rounds=s.online_rounds,
        replay_rounds=s.replay_rounds, beta1=s.beta1, beta2=s.beta2,
    )
    reports = ResearchRunner(engine, store).run(args.task, args.iterations, seed=s.random_seed)
    print(json.dumps([r.__dict__ for r in reports], indent=2, default=str))
    store.close()


if __name__ == '__main__':
    main()
