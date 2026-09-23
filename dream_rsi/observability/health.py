from __future__ import annotations
from time import time
class WorkerHeartbeat:
    def __init__(self,store,worker_id): self.store,self.worker_id=store,worker_id
    def beat(self):
        fn=getattr(self.store,"heartbeat_worker",None)
        if fn: fn(self.worker_id,time())
