from __future__ import annotations
import hashlib
from dataclasses import dataclass
from typing import Any, Sequence
from .base import PrefixPolicy
from .registry import PolicyRegistry
from ..llm.client import LLMClient, extract_json
from ..research.protocol import json_schema_prompt

@dataclass
class LLMPolicyDeveloper:
    llm: LLMClient
    registry: PolicyRegistry
    max_source_chars: int = 16000

    def propose(self, current: PrefixPolicy, feedback: Sequence[dict[str, Any]]):
        compact = {"current_policy": current.name, "feedback": list(feedback)}
        system = (
            "You are a research policy developer for Dream-RSI. Improve ONLY the exploration policy. "
            "It must implement reset() and select_batch(view,max_parallelism). The view exposes only observed nodes. "
            "Never inspect the underlying tree. Do not use I/O, imports, networking, subprocesses, eval, exec, compile, "
            "reflection, randomness, or hidden global state. Keep the policy deterministic and stateless except for resettable state. "
            + json_schema_prompt()
        )
        response = self.llm.generate([
            {"role":"system","content":system},
            {"role":"user","content":str(compact)},
        ], temperature=0.2, max_tokens=5000, response_format="json")
        data=extract_json(response.text)
        name=str(data.get("name") or "policy_"+hashlib.sha1(response.text.encode()).hexdigest()[:8])
        source=str(data.get("source") or "")
        if len(source)>self.max_source_chars: raise ValueError("generated policy is too large")
        self.registry.validate_source(source)
        ns={"__name__":"generated_policy","PrefixPolicy":PrefixPolicy,"__builtins__":{"__build_class__":__build_class__,"object":object,"len":len,"min":min,"max":max,"sorted":sorted,"list":list,"set":set,"float":float,"range":range,"abs":abs,"tuple":tuple}}
        exec(compile(source,"<generated-policy>","exec"),ns,ns)
        classes=[v for v in ns.values() if isinstance(v,type) and issubclass(v,PrefixPolicy) and v is not PrefixPolicy]
        if not classes: raise ValueError("generated policy must subclass PrefixPolicy")
        policy=classes[-1]()
        policy.name=name
        policy.source=source
        policy.rationale=str(data.get("rationale") or "")
        return policy
