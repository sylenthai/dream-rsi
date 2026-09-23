from __future__ import annotations
import argparse, os
from ..service.worker import ExperimentWorker
from ..service.queue import InMemoryJobQueue, RedisJobQueue
from ..service.handlers import build_handlers
from ..storage import RunStore, PostgresRunStore

def main() -> None:
    p=argparse.ArgumentParser(description="Dream-RSI distributed worker")
    p.add_argument("--once", action="store_true")
    p.add_argument("--max-attempts", type=int, default=int(os.getenv("DREAM_RSI_MAX_ATTEMPTS", "3")))
    a=p.parse_args()
    dsn=os.getenv("DREAM_RSI_POSTGRES_DSN")
    store=PostgresRunStore(dsn) if dsn else RunStore(os.getenv("DREAM_RSI_DB", "runs/dream_rsi.sqlite3"))
    redis_url=os.getenv("DREAM_RSI_REDIS_URL")
    q=RedisJobQueue(redis_url) if redis_url else InMemoryJobQueue()
    worker=ExperimentWorker(store, q, build_handlers(), max_attempts=a.max_attempts)
    if a.once: worker.process_once()
    else: worker.run_forever()
