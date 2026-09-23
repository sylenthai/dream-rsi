from __future__ import annotations
import hashlib, json, platform, sys
from dataclasses import asdict, dataclass
@dataclass(frozen=True)
class Manifest:
    python:str; platform:str; package_version:str; seed:int; config:dict
    def write(self,path):
        with open(path,'w',encoding='utf-8') as f: json.dump(asdict(self),f,indent=2,sort_keys=True)
def source_hash(root='dream_rsi'):
    h=hashlib.sha256()
    import pathlib
    for p in sorted(pathlib.Path(root).rglob('*.py')): h.update(str(p).encode()); h.update(p.read_bytes())
    return h.hexdigest()
def build_manifest(config,seed=42): return Manifest(sys.version,platform.platform(),'3.3.1',seed,dict(config))
