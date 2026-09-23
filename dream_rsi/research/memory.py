from __future__ import annotations
import json, sqlite3, threading, time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class ResearchMemory:
    key: str
    value: dict[str, Any]
    created_at: float

class ResearchMemoryStore:
    """Persistent, append-friendly research memory backed by SQLite."""
    def __init__(self, path: str | Path = "dream_rsi_memory.sqlite3"):
        self.path = str(path)
        p = Path(self.path)
        if p.parent and not p.parent.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init()

    def _init(self):
        with self._lock:
            self.conn.execute("CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, value TEXT, created_at REAL)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key)")
            self.conn.commit()

    def put(self, key: str, value: dict[str, Any]) -> ResearchMemory:
        item = ResearchMemory(key, dict(value), time.time())
        with self._lock:
            self.conn.execute("INSERT INTO memories(key,value,created_at) VALUES(?,?,?)", (key, json.dumps(item.value, ensure_ascii=False), item.created_at))
            self.conn.commit()
        return item

    def recent(self, key: str | None = None, limit: int = 20) -> list[ResearchMemory]:
        q = "SELECT key,value,created_at FROM memories"
        args: list[Any] = []
        if key is not None:
            q += " WHERE key=?"; args.append(key)
        q += " ORDER BY id DESC LIMIT ?"; args.append(limit)
        with self._lock:
            rows = self.conn.execute(q, args).fetchall()
        return [ResearchMemory(k, json.loads(v), ts) for k,v,ts in rows]

    def summary(self, limit: int = 50) -> dict[str, Any]:
        rows = self.recent(limit=limit)
        return {"count": len(rows), "keys": sorted({r.key for r in rows}), "items": [asdict(r) for r in rows]}

    def close(self):
        with self._lock:
            self.conn.close()
