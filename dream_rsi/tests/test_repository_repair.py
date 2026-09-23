from pathlib import Path
from dream_rsi.llm.client import LLMResponse
from dream_rsi.repository.repair import RepositoryRepairAgent
from dream_rsi.repository.runner import RepositoryRunner

class FakeLLM:
    model='fake-repair'
    def generate(self,messages,**kwargs):
        return LLMResponse('{"files":[{"path":"app.py","content":"x = 2\\n","operation":"write"}],"rationale":"fix value"}',self.model)

def test_failure_driven_repair(tmp_path):
    (tmp_path/'app.py').write_text('x = 1\n')
    (tmp_path/'test.py').write_text('from app import x\nassert x == 2\n')
    report=RepositoryRepairAgent(FakeLLM(), RepositoryRunner(prefer_docker=False)).run('fix x',tmp_path,('python','test.py'),max_attempts=2)
    assert report.success and report.attempts==2
