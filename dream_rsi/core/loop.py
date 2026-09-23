from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from .tree import DiscoveryTree
from .world import ReplayWorld
from .interfaces import DiscoveryAgent, Evaluator, ExplorationPolicy, PolicyDeveloper

@dataclass
class IterationReport:
    iteration:int
    world_id:str
    candidate_scores:list[tuple[str,float]]
    selected_policy:str
    best_replay_score:float
    fresh_validation:dict[str,Any]=field(default_factory=dict)
    candidate_rejections:dict[str,str]=field(default_factory=dict)

@dataclass
class DreamRSI:
    agent:DiscoveryAgent
    policy_developer:PolicyDeveloper
    policy:ExplorationPolicy
    evaluator:Evaluator|None=None
    fresh_validator:Any|None=None
    workers:int=4
    online_rounds:int=20
    replay_rounds:int=100
    beta1:float=.01
    beta2:float=.02
    min_fresh_delta:float=0.0
    history:list[DiscoveryTree]=field(default_factory=list)

    def online_rollout(self, policy=None)->DiscoveryTree:
        active = policy or self.policy
        tree=DiscoveryTree(); active.reset()
        for _ in range(self.online_rounds):
            view=tree.clone_view(); batch=list(dict.fromkeys(active.select_batch(view,self.workers)))
            if not batch: break
            legal=set(view.eligible())
            if len(batch)>self.workers or any(x not in legal for x in batch):
                raise ValueError(f"Illegal online batch: {batch}")
            def run_one(parent_id):
                result=self.agent.generate(parent_id,{"tree":tree,"parent_id":parent_id})
                return self.evaluator.evaluate(result) if self.evaluator else result
            with ThreadPoolExecutor(max_workers=min(self.workers,len(batch))) as pool:
                futures={pool.submit(run_one,p):p for p in batch}
                results={futures[f]:f.result() for f in as_completed(futures)}
            for parent_id in batch:
                result=results[parent_id]
                tree.add_child(parent_id,result.score,result.success,dict(result.diagnostics or {}))
        return tree

    def _evaluate(self, policy):
        results=[ReplayWorld(f"world-{i+1}",tree).run(policy,self.workers,self.replay_rounds,self.beta1,self.beta2) for i,tree in enumerate(self.history)]
        avg=sum(r.metrics.reward for r in results)/max(1,len(results))
        return avg,results

    def dream(self,candidate_policies):
        policies=[self.policy]+[p for p in candidate_policies if p.name!=self.policy.name]
        reports=[(p,*self._evaluate(p)) for p in policies]
        selected,avg,results=max(reports,key=lambda x:x[1])
        return selected,reports,results

    def _fresh(self, policy):
        if not self.fresh_validator:
            return None
        return self.fresh_validator.validate(policy)

    def run_iteration(self,iteration:int)->IterationReport:
        tree=self.online_rollout(); self.history.append(tree)
        current_avg,current_results=self._evaluate(self.policy)
        feedback=[{"policy":self.policy.name,"avg_reward":current_avg,"worlds":[asdict(r.metrics) for r in current_results]}]
        try: candidate=self.policy_developer.propose(self.policy,feedback)
        except Exception as exc: candidate=None; feedback.append({"developer_error":str(exc)})
        candidates=[candidate] if candidate is not None else []
        selected,reports,replay_results=self.dream(candidates)
        fresh={}; rejections={}
        if self.fresh_validator:
            current_fresh=self._fresh(self.policy)
            fresh[self.policy.name]=asdict(current_fresh)
            if candidate is not None:
                candidate_fresh=self._fresh(candidate)
                fresh[candidate.name]=asdict(candidate_fresh)
                if selected.name==candidate.name and candidate_fresh.score < current_fresh.score + self.min_fresh_delta:
                    rejections[candidate.name]=f"fresh score {candidate_fresh.score:.6f} < required {current_fresh.score + self.min_fresh_delta:.6f}"
                    selected=self.policy
        self.policy=selected
        scores=[(p.name,avg) for p,avg,_ in reports]
        best=max((r.metrics.reward for r in replay_results),default=float('-inf'))
        return IterationReport(iteration,f"world-{len(self.history)}",scores,selected.name,best,fresh,rejections)
