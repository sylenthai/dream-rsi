from dream_rsi.core.loop import DreamRSI
from dream_rsi.policies.heuristic import ConservativePolicy
from dream_rsi.policies.mutator import PolicyMutator
from dream_rsi.adapters.toy import ToyDiscoveryAgent


def main():
    system = DreamRSI(
        agent=ToyDiscoveryAgent(),
        policy_developer=PolicyMutator(),
        policy=ConservativePolicy(beta=0.35),
        workers=4,
        online_rounds=12,
        replay_rounds=30,
    )
    for i in range(1, 4):
        report = system.run_iteration(i)
        print(f"iteration={i} world={report.world_id} selected={report.selected_policy}")
        for name, score in report.candidate_scores:
            print(f"  {name:14s} replay_sum={score:.6f}")
        print(f"  best_world_reward={report.best_replay_score:.6f}\n")


if __name__ == "__main__":
    main()
