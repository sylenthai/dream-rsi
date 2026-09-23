from __future__ import annotations
import json, logging, time
class EventLog:
    def __init__(self, name="dream_rsi"):
        self.log=logging.getLogger(name); self.log.setLevel(logging.INFO)
        if not self.log.handlers:
            h=logging.StreamHandler(); h.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s')); self.log.addHandler(h)
    def emit(self, event, **data):
        payload={"event":event,"ts":time.time(),**data}; self.log.info(json.dumps(payload, sort_keys=True, default=str))
