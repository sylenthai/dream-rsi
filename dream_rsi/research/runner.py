from __future__ import annotations
from dataclasses import asdict
from uuid import uuid4
from ..core.loop import DreamRSI
from ..storage.sqlite import RunStore
from ..observability.events import EventLog
from .manifest import build_manifest, source_hash

class ResearchRunner:
    def __init__(self, engine:DreamRSI, store:RunStore, logger=None):
        self.engine=engine; self.store=store; self.log=logger or EventLog(); self.run_id=str(uuid4())
    def run(self, task='unnamed', iterations=3, seed=42):
        cfg={'workers':self.engine.workers,'online_rounds':self.engine.online_rounds,'replay_rounds':self.engine.replay_rounds,'beta1':self.engine.beta1,'beta2':self.engine.beta2,'min_fresh_delta':self.engine.min_fresh_delta}
        manifest=build_manifest(cfg,seed); cfg['source_hash']=source_hash()
        self.store.create_run(self.run_id,task,{**cfg,'manifest':asdict(manifest)})
        reports=[]
        for i in range(1,iterations+1):
            self.log.emit('iteration_start',run_id=self.run_id,iteration=i)
            report=self.engine.run_iteration(i); reports.append(report)
            self.store.save_world(self.run_id,report.world_id,self.engine.history[-1])
            self.store.save_iteration(self.run_id,i,report.selected_policy,asdict(report))
            self.store.save_policy(self.run_id,report.selected_policy,getattr(self.engine.policy,'source',''),{'iteration':i})
            self.log.emit('iteration_end',run_id=self.run_id,iteration=i,policy=report.selected_policy,best=report.best_replay_score)
        return reports
