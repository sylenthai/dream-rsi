from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping, Protocol
import json


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw: Mapping[str, Any] | None = None


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    model: str

    def generate(self, messages: list[dict[str, str]], *, temperature: float = 0.2,
                 max_tokens: int = 2048, response_format: str | None = None) -> LLMResponse: ...


def extract_json(text: str) -> Any:
    """Parse JSON from strict JSON output or a fenced JSON block."""
    raw = text.strip()
    if raw.startswith('```'):
        lines = raw.splitlines()
        if lines and lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        raw = '\n'.join(lines).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError(f'LLM did not return valid JSON: {exc}') from exc
