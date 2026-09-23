from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

@dataclass(frozen=True)
class FilePatch:
    path: str
    content: str
    operation: str = 'write'

@dataclass(frozen=True)
class PatchSet:
    files: tuple[FilePatch, ...]
    rationale: str = ''
    model: str = ''
    def manifest(self): return {'files':[asdict(x) for x in self.files], 'rationale':self.rationale, 'model':self.model}

def apply_patchset(root: str|Path, patchset: PatchSet) -> list[str]:
    root=Path(root).resolve(); changed=[]
    for patch in patchset.files:
        target=(root/patch.path).resolve()
        if root not in target.parents and target != root: raise ValueError(f'path escapes repository: {patch.path}')
        if patch.operation == 'delete':
            if target.exists(): target.unlink(); changed.append(patch.path)
        elif patch.operation == 'write':
            target.parent.mkdir(parents=True, exist_ok=True); target.write_text(patch.content, encoding='utf-8'); changed.append(patch.path)
        else: raise ValueError(f'unsupported patch operation: {patch.operation}')
    return changed
