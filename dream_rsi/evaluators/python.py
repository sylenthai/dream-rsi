from __future__ import annotations
import ast, math
from typing import Any
from ..core.interfaces import CandidateResult
from ..execution.python_sandbox import PythonSandbox
class PythonCodeEvaluator:
    def __init__(self, sandbox: PythonSandbox | None = None): self.sandbox=sandbox or PythonSandbox()
    def evaluate(self,candidate:CandidateResult)->CandidateResult:
        artifact=(candidate.diagnostics or {}).get('artifact',{})
        code=artifact.get('solution') if isinstance(artifact,dict) else None
        if not isinstance(code,str): return CandidateResult(-math.inf,False,{"error":"missing solution"})
        try:
            tree=ast.parse(code)
            if any(isinstance(n,(ast.Import,ast.ImportFrom)) for n in ast.walk(tree)):
                return CandidateResult(-math.inf,False,{"error":"imports are disabled"})
        except SyntaxError as exc: return CandidateResult(-math.inf,False,{"error":f"syntax: {exc}"})
        result=self.sandbox.run(code)
        if result.timed_out or result.returncode!=0:
            return CandidateResult(-math.inf,False,{"returncode":result.returncode,"stderr":result.stderr,"stdout":result.stdout,"duration_s":result.duration_s})
        return CandidateResult(1.0/max(result.duration_s,1e-6),True,{"stdout":result.stdout,"stderr":result.stderr,"duration_s":result.duration_s,"artifact":artifact})
