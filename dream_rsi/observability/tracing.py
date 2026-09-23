from __future__ import annotations
from contextlib import contextmanager
try:
    from opentelemetry import trace
    _TRACER=trace.get_tracer("dream-rsi")
except Exception:
    _TRACER=None

@contextmanager
def span(name,**attributes):
    if _TRACER is None:
        yield None; return
    with _TRACER.start_as_current_span(name) as s:
        for k,v in attributes.items(): s.set_attribute(k,str(v))
        yield s
