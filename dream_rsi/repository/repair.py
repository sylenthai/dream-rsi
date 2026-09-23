from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping
from ..llm.client import LLMClient, extract_json
from ..research.memory import ResearchMemoryStore
from .diagnostics import FailureLocalizer, FailureDiagnosis
from .patching import FilePatch, PatchSet
from .runner import RepositoryRunner, RepositoryRunResult

@dataclass(frozen=True)
class RepairAttempt:
    attempt: int
    diagnosis: dict[str, Any]
    patch: dict[str, Any] | None
    result: dict[str, Any]

@dataclass(frozen=True)
class RepairReport:
    task: str
    model: str
    success: bool
    attempts: int
    final: dict[str, Any]
    history: tuple[RepairAttempt, ...]
    def manifest(self): return asdict(self)

class RepositoryRepairAgent:
    """Failure-driven repository repair loop. The model proposes patches; the runner alone executes/tests them."""
    def __init__(self, llm: LLMClient, runner: RepositoryRunner | None = None, memory: ResearchMemoryStore | None = None, localizer: FailureLocalizer | None = None):
        self.llm=llm; self.runner=runner or RepositoryRunner(); self.memory=memory; self.localizer=localizer or FailureLocalizer()
    def _context(self, root: Path, diagnosis: FailureDiagnosis, result: RepositoryRunResult):
        files={}
        for p in sorted(root.rglob('*')):
            if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts and p.stat().st_size <= 20000:
                files[str(p.relative_to(root))]=p.read_text(encoding='utf-8',errors='replace')[:12000]
                if len(files)>=30: break
        return {'failure':diagnosis.manifest(),'test_result':result.manifest(),'files':files}
    def _ask(self, task, context):
        r=self.llm.generate([
          {'role':'system','content':('You are a repository repair agent. Return ONLY JSON: '
            '{"files":[{"path":"...","content":"...","operation":"write|delete"}],"rationale":"..."}. '
            'Only modify files needed for the observed failure. Never claim tests passed; the runner verifies them. '
            'Never use absolute paths or ../ paths.')},
          {'role':'user','content':json.dumps({'task':task,'context':context},ensure_ascii=False)}
        ],temperature=0.0,max_tokens=12000,response_format='json')
        data=extract_json(r.text)
        if not isinstance(data,dict) or not isinstance(data.get('files'),list): raise ValueError('repair LLM returned invalid patch JSON')
        patches=[]
        for f in data['files']:
            if not isinstance(f,dict): raise ValueError('invalid patch entry')
            patches.append(FilePatch(str(f['path']),str(f.get('content','')),str(f.get('operation','write'))))
        return PatchSet(tuple(patches),str(data.get('rationale','')),r.model)
    def run(self, task: str, repository: str|Path, command: tuple[str,...], max_attempts=3) -> RepairReport:
        # Each attempt gets a clean copy through RepositoryRunner; patches are carried forward.
        pending: list[FilePatch]=[]; history=[]; last=None
        for i in range(1,max_attempts+1):
            patchset=PatchSet(tuple(pending), rationale='carried repairs') if pending else None
            result=self.runner.run(repository,command,patchset)
            last=result
            if result.success:
                history.append(RepairAttempt(i,{'category':'none','confidence':1.0,'summary':'tests passed','evidence':(),'suggested_files':result.changed_files}, patchset.manifest() if patchset else None,result.manifest()))
                report=RepairReport(task,self.llm.model,True,i,result.manifest(),tuple(history))
                if self.memory: self.memory.put('repository_repair',report.manifest())
                return report
            diagnosis=self.localizer.diagnose(result.stdout,result.stderr,result.changed_files)
            # Build context from a materialized clean repository plus currently proposed files.
            from tempfile import TemporaryDirectory
            import shutil
            with TemporaryDirectory(prefix='dream-rsi-repair-context-') as td:
                root=Path(td)/'repo'; shutil.copytree(repository,root,ignore=shutil.ignore_patterns('.git','__pycache__'))
                for f in pending:
                    target=(root/f.path).resolve()
                    if root not in target.parents: raise ValueError(f'unsafe carried patch: {f.path}')
                    if f.operation=='write': target.parent.mkdir(parents=True,exist_ok=True); target.write_text(f.content,encoding='utf-8')
                patch=self._ask(task,self._context(root,diagnosis,result))
            patch_dict = {p.path: p for p in pending}
            for p in patch.files:
                patch_dict[p.path] = p
            pending = list(patch_dict.values())
            history.append(RepairAttempt(i,diagnosis.manifest(),patch.manifest(),result.manifest()))
            if self.memory: self.memory.put('repair_attempt',{'task':task,'attempt':i,'diagnosis':diagnosis.manifest(),'patch':patch.manifest(),'result':result.manifest()})
        report=RepairReport(task,self.llm.model,False,max_attempts,last.manifest() if last else {},tuple(history))
        if self.memory: self.memory.put('repository_repair',report.manifest())
        return report
