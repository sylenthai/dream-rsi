from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
import json
@dataclass(frozen=True)
class Candidate:
    code:str; rationale:str=""; metadata:dict[str,Any]|None=None
@dataclass(frozen=True)
class Validation:
    accepted:bool; replay_score:float; fresh_score:float; reason:str
    def to_dict(self): return asdict(self)
def json_schema_prompt()->str:
    return 'Return ONLY JSON: {"name": string, "source": string, "rationale": string}. source must be a Python policy class using the PrefixPolicy interface.'
def safe_json(text:str):
    text=text.strip()
    if text.startswith('```'): text=text.strip('`').replace('json\n','',1).strip()
    return json.loads(text)
