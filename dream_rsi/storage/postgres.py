from __future__ import annotations
import json
import threading
from datetime import datetime, timezone
from typing import Any

class PostgresRunStore:
    """PostgreSQL-backed run store. Requires the optional database extra."""
    def __init__(self, dsn: str):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("Install the database extra: pip install 'dream-rsi[database]'") from exc
        self._psycopg = psycopg
        from psycopg.types.json import Jsonb
        psycopg.types.json.Jsonb = Jsonb
        self._lock = threading.Lock()
        self.conn = psycopg.connect(dsn)
        with self._lock:
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS runs(
              id TEXT PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL, task TEXT NOT NULL,
              config JSONB NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
              result JSONB, error TEXT, updated_at TIMESTAMPTZ NOT NULL
            )
            """)
            self.conn.commit()

    def healthcheck(self) -> None:
        with self._lock:
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()

    def create_run(self, run_id: str, task: str, config: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self.conn.execute("INSERT INTO runs(id,created_at,task,config,status,updated_at) VALUES(%s,%s,%s,%s,%s,%s)",
                              (run_id, now, task, self._psycopg.types.json.Jsonb(config), "queued", now))
            self.conn.commit()

    def find_by_idempotency(self, key: str):
        with self._lock:
            row = self.conn.execute("SELECT id FROM runs WHERE config->>'_idempotency_key'=%s LIMIT 1", (key,)).fetchone()
        return self.get_run(row[0]) if row else None

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute("SELECT id,task,config,status,attempts,result,error,created_at,updated_at FROM runs WHERE id=%s", (run_id,)).fetchone()
        if not row: return None
        return dict(zip(("id","task","config","status","attempts","result","error","created_at","updated_at"), row))

    def update_run(self, run_id: str, status: str, *, attempts: int | None = None,
                   result: dict[str, Any] | None = None, error: str | None = None) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self.conn.execute("""UPDATE runs SET status=%s, attempts=COALESCE(%s,attempts), result=COALESCE(%s,result), error=%s, updated_at=%s WHERE id=%s""",
                              (status, attempts, self._psycopg.types.json.Jsonb(result) if result is not None else None, error, now, run_id))
            self.conn.commit()

    def heartbeat_worker(self, worker_id: str, heartbeat: float) -> None:
        with self._lock:
            self.conn.execute("CREATE TABLE IF NOT EXISTS worker_heartbeats(worker_id TEXT PRIMARY KEY, heartbeat DOUBLE PRECISION NOT NULL)")
            self.conn.execute("INSERT INTO worker_heartbeats(worker_id,heartbeat) VALUES(%s,%s) ON CONFLICT(worker_id) DO UPDATE SET heartbeat=EXCLUDED.heartbeat", (worker_id, heartbeat))
            self.conn.commit()

    def stale_runs(self, cutoff: float) -> list[str]:
        with self._lock:
            rows = self.conn.execute("SELECT id FROM runs WHERE status='running' AND EXTRACT(EPOCH FROM updated_at) < %s", (cutoff,)).fetchall()
        return [r[0] for r in rows]

    def close(self) -> None:
        with self._lock:
            self.conn.close()
