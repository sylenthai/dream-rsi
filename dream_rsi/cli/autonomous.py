from __future__ import annotations
import argparse
from ..llm.factory import create_llm
from ..research.memory import ResearchMemoryStore
from ..research.task_registry import default_coding_registry
from ..research.autonomous import AutonomousResearchLoop, save_autonomous

def main():
    p=argparse.ArgumentParser(description='Dream-RSI autonomous failure-driven research loop')
    p.add_argument('--provider',choices=['ollama','openai','openai-compatible','gemini'],default='ollama')
    p.add_argument('--model',default=None); p.add_argument('--cycles',type=int,default=3)
    p.add_argument('--task',default='sum-two'); p.add_argument('--memory',default='dream_rsi_memory.sqlite3')
    p.add_argument('--output',default='autonomous-report.json'); a=p.parse_args()
    llm=create_llm(a.provider,model=a.model)
    reg=default_coding_registry(); task=reg.get(a.task)
    report=AutonomousResearchLoop(llm,ResearchMemoryStore(a.memory),reg).run(task,cycles=a.cycles)
    save_autonomous(a.output,report); print(a.output)
if __name__=='__main__': main()
