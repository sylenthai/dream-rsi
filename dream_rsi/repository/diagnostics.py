from __future__ import annotations
import re
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class FailureDiagnosis:
    category: str
    confidence: float
    summary: str
    evidence: tuple[str,...]
    suggested_files: tuple[str,...]
    def manifest(self): return asdict(self)

class FailureLocalizer:
    """Deterministic first-pass failure localization. It never claims semantic certainty."""
    PATTERNS=(
      ('syntax', re.compile(r'SyntaxError|IndentationError|TabError')),
      ('import', re.compile(r'ModuleNotFoundError|ImportError|No module named')),
      ('assertion', re.compile(r'AssertionError|assert ')),
      ('type', re.compile(r'TypeError')),
      ('name', re.compile(r'NameError|UnboundLocalError')),
      ('attribute', re.compile(r'AttributeError')),
      ('timeout', re.compile(r'timeout|timed out|Timeout',re.I)),
    )
    def diagnose(self, stdout='', stderr='', changed_files=()):
        text=(stderr or '')+'\n'+(stdout or '')
        category='unknown'; confidence=0.25
        for name,pat in self.PATTERNS:
            if pat.search(text): category=name; confidence=0.85; break
        evidence=tuple(x.strip() for x in text.splitlines() if x.strip())[-5:]
        suggested=tuple(changed_files)
        if category in {'syntax','type','name','attribute','assertion'}: confidence=min(0.95,confidence+0.05)
        return FailureDiagnosis(category,confidence, f'Observed failure category: {category}', evidence, suggested)
