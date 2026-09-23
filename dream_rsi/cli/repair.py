from __future__ import annotations
import argparse, json
from pathlib import Path
from ..llm.factory import create_llm
from ..repository.repair import RepositoryRepairAgent

def main():
    p=argparse.ArgumentParser(description='Dream-RSI failure-driven repository repair')
    p.add_argument('--provider',default='ollama',choices=['ollama','openai','openai-compatible','gemini'])
    p.add_argument('--model',default=None); p.add_argument('--repository',required=True); p.add_argument('--task',required=True)
    p.add_argument('--command',nargs='+',required=True); p.add_argument('--attempts',type=int,default=3); p.add_argument('--output',default='repair-report.json')
    a=p.parse_args(); llm=create_llm(a.provider,model=a.model); report=RepositoryRepairAgent(llm).run(a.task,a.repository,tuple(a.command),a.attempts)
    Path(a.output).write_text(json.dumps(report.manifest(),indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(report.manifest(),indent=2,ensure_ascii=False))
if __name__=='__main__': main()
