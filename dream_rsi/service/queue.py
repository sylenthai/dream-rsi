from __future__ import annotations
import json, queue, time, os
from dataclasses import dataclass
from typing import Any, Protocol

@dataclass(frozen=True)
class Job:
    run_id: str
    task: str
    config: dict[str, Any]
    attempt: int = 0
    queue_id: str | None = None

class JobQueue(Protocol):
    def enqueue(self, job: Job) -> None: ...
    def dequeue(self, timeout: float = 1.0) -> Job | None: ...

class InMemoryJobQueue:
    def __init__(self): self._q: queue.Queue[Job] = queue.Queue()
    def enqueue(self, job: Job) -> None: self._q.put(job)
    def dequeue(self, timeout: float = 1.0) -> Job | None:
        try: return self._q.get(timeout=timeout)
        except queue.Empty: return None
    def ack(self, job: Job) -> None: return None
    def healthcheck(self) -> None: return None
    def reclaim_stale(self, *args, **kwargs) -> list[Job]: return []
    def dead_letter(self, job: Job, reason: str) -> None: return None

class RedisJobQueue:
    """Redis Streams queue with consumer groups, stale-message reclamation and DLQ."""
    def __init__(self, url: str, stream: str = "dream-rsi:jobs", group: str = "workers", consumer: str | None = None, visibility_timeout: float = 60.0):
        try: import redis
        except ImportError as exc: raise RuntimeError("Install the queue extra: pip install 'dream-rsi[queue]'") from exc
        self.redis=redis.Redis.from_url(url,decode_responses=True); self.stream=stream; self.group=group
        self.consumer=consumer or os.getenv("HOSTNAME") or f"worker-{os.getpid()}"; self.visibility_timeout=visibility_timeout; self.dlq=f"{stream}:dead-letter"
        try: self.redis.xgroup_create(self.stream,self.group,id="0",mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc): raise
    def healthcheck(self) -> None:
        self.redis.ping()

    def enqueue(self, job: Job) -> None:
        self.redis.xadd(self.stream,{"run_id":job.run_id,"task":job.task,"config":json.dumps(job.config),"attempt":str(job.attempt)})
    def ack(self, job: Job) -> None:
        if job.queue_id: self.redis.xack(self.stream,self.group,job.queue_id)
    def dequeue(self, timeout: float = 1.0) -> Job | None:
        rows=self.redis.xreadgroup(self.group,self.consumer,{self.stream:">"},count=1,block=max(1,int(timeout*1000)))
        if not rows:return None
        _,messages=rows[0]; mid,fields=messages[0]
        return Job(fields["run_id"],fields["task"],json.loads(fields["config"]),int(fields.get("attempt",0)),mid)
    def reclaim_stale(self, min_idle_ms: int | None = None, count: int = 100) -> list[Job]:
        idle=min_idle_ms if min_idle_ms is not None else int(self.visibility_timeout*1000)
        try: rows=self.redis.xautoclaim(self.stream,self.group,self.consumer,idle,"0-0",count=count)
        except AttributeError: return []
        messages=rows[1] if isinstance(rows,(tuple,list)) and len(rows)>1 else []
        out=[]
        for mid,fields in messages:
            out.append(Job(fields["run_id"],fields["task"],json.loads(fields["config"]),int(fields.get("attempt",0)),mid))
        return out
    def dead_letter(self, job: Job, reason: str) -> None:
        self.redis.xadd(self.dlq,{"run_id":job.run_id,"task":job.task,"config":json.dumps(job.config),"attempt":str(job.attempt),"reason":reason,"failed_at":str(time.time())})
