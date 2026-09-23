from __future__ import annotations
import json, sqlite3, threading
from pathlib import Path
from datetime import datetime, timezone

class RunStore:
    def __init__(self, path: str):
        self.path=Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock=threading.Lock(); self.conn=sqlite3.connect(self.path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL"); self.conn.execute("PRAGMA foreign_keys=ON")
        self._migrate(); self._create_tables()
    def _migrate(self):
        cols={r[1] for r in self.conn.execute("PRAGMA table_info(runs)")}
        additions={"status":"TEXT NOT NULL DEFAULT 'queued'","attempts":"INTEGER NOT NULL DEFAULT 0","result":"TEXT","error":"TEXT","updated_at":"TEXT"}
        for name,spec in additions.items():
            if cols and name not in cols: self.conn.execute(f"ALTER TABLE runs ADD COLUMN {name} {spec}")
        self.conn.commit()
    def _create_tables(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, task TEXT NOT NULL, config TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0, result TEXT, error TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS iterations(run_id TEXT, iteration INTEGER, policy TEXT, report TEXT, PRIMARY KEY(run_id,iteration));
        CREATE TABLE IF NOT EXISTS nodes(run_id TEXT, world_id TEXT, node_id TEXT, parent_id TEXT, depth INTEGER, created_order INTEGER, score REAL, success INTEGER, diagnostics TEXT, PRIMARY KEY(run_id,world_id,node_id));
        CREATE TABLE IF NOT EXISTS policies(run_id TEXT, name TEXT, source TEXT, metadata TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(run_id,name));
        CREATE TABLE IF NOT EXISTS worker_heartbeats(worker_id TEXT PRIMARY KEY, heartbeat REAL NOT NULL);
        """); self.conn.commit()
    def healthcheck(self):
        self.conn.execute("SELECT 1").fetchone()

    def create_run(self,run_id,task,config):
        now=datetime.now(timezone.utc).isoformat()
        with self._lock: self.conn.execute("INSERT INTO runs(id,created_at,task,config,status,attempts,updated_at) VALUES(?,?,?,?,?,?,?)",(run_id,now,task,json.dumps(config),"queued",0,now)); self.conn.commit()
    def get_run(self,run_id):
        row=self.conn.execute("SELECT id,task,config,status,attempts,result,error,created_at,updated_at FROM runs WHERE id=?",(run_id,)).fetchone()
        if not row:return None
        vals=list(row); vals[2]=json.loads(vals[2]); vals[5]=json.loads(vals[5]) if vals[5] else None
        return dict(zip(("id","task","config","status","attempts","result","error","created_at","updated_at"),vals))
    def find_by_idempotency(self, key: str):
        try:
            with self._lock:
                row = self.conn.execute(
                    "SELECT id FROM runs WHERE json_extract(config, '$._idempotency_key') = ? LIMIT 1",
                    (key,)
                ).fetchone()
            if row:
                return self.get_run(row[0])
        except sqlite3.OperationalError:
            with self._lock:
                rows = self.conn.execute("SELECT id, config FROM runs").fetchall()
            for rid, cfg in rows:
                try:
                    if json.loads(cfg).get("_idempotency_key") == key:
                        return self.get_run(rid)
                except Exception:
                    continue
        return None
    def update_run(self,run_id,status,*,attempts=None,result=None,error=None):
        with self._lock:self.conn.execute("UPDATE runs SET status=?,attempts=COALESCE(?,attempts),result=COALESCE(?,result),error=?,updated_at=? WHERE id=?",(status,attempts,json.dumps(result) if result is not None else None,error,datetime.now(timezone.utc).isoformat(),run_id));self.conn.commit()
    def save_iteration(self,run_id,iteration,policy,report):
        with self._lock:self.conn.execute("INSERT OR REPLACE INTO iterations VALUES(?,?,?,?)",(run_id,iteration,policy,json.dumps(report)));self.conn.commit()
    def save_world(self,run_id,world_id,tree):
        rows=[(run_id,world_id,n.id,n.parent_id,n.depth,n.created_order,n.score,int(n.success),json.dumps(n.diagnostics)) for n in tree.nodes.values()]
        with self._lock:self.conn.executemany("INSERT OR REPLACE INTO nodes VALUES(?,?,?,?,?,?,?,?,?)",rows);self.conn.commit()
    def save_policy(self,run_id,name,source,metadata=None):
        with self._lock:self.conn.execute("INSERT OR REPLACE INTO policies(run_id,name,source,metadata) VALUES(?,?,?,?)",(run_id,name,source,json.dumps(metadata or {})));self.conn.commit()
    def heartbeat_worker(self,worker_id,heartbeat):
        with self._lock:self.conn.execute("INSERT OR REPLACE INTO worker_heartbeats(worker_id,heartbeat) VALUES(?,?)",(worker_id,heartbeat));self.conn.commit()
    def stale_runs(self,cutoff):
        return [r[0] for r in self.conn.execute("SELECT id FROM runs WHERE status='running' AND updated_at < ?",(datetime.fromtimestamp(cutoff,timezone.utc).isoformat(),))]
    def close(self):self.conn.close()
