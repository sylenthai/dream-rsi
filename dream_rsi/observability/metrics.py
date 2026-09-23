from __future__ import annotations
from collections import Counter
from threading import Lock
from time import perf_counter

class Metrics:
    def __init__(self):
        self._lock=Lock(); self.counters=Counter(); self.durations=[]
    def inc(self,name,value=1,**labels):
        key=(name,tuple(sorted(labels.items())))
        with self._lock:self.counters[key]+=value
    def observe(self,name,value,**labels):
        key=(name,tuple(sorted(labels.items())))
        with self._lock:self.durations.append((key,float(value)))
    def prometheus(self)->str:
        out=[]
        with self._lock:
            for (name,labels),value in sorted(self.counters.items()):
                ls=','.join(f'{k}="{str(v).replace(chr(92),chr(92)+chr(92)).replace(chr(34),chr(92)+chr(34))}"' for k,v in labels)
                out.append(f'{name}{{{ls}}} {value}' if ls else f'{name} {value}')
            grouped={}
            for (name,labels),value in self.durations:
                grouped.setdefault((name,labels),[]).append(value)
            for (name,labels),vals in grouped.items():
                ls=','.join(f'{k}="{v}"' for k,v in labels)
                metric_name=f'{name}_count'; prefix=f'{metric_name}{{{ls}}}' if ls else metric_name
                out.append(f'{prefix} {len(vals)}')
                metric_name=f'{name}_sum'; prefix=f'{metric_name}{{{ls}}}' if ls else metric_name
                out.append(f'{prefix} {sum(vals):.6f}')
        return '\n'.join(out)+'\n'

METRICS=Metrics()
class Timer:
    def __init__(self,name,**labels): self.name,self.labels,self.start=name,labels,perf_counter()
    def observe(self): METRICS.observe(self.name,perf_counter()-self.start,**self.labels)
