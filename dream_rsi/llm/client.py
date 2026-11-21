from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping, Protocol
import json
import re


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
    """Parse JSON from strict JSON output, reasoning-prefixed prose, or fenced JSON blocks."""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # 1. Fast path: raw JSON string
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as first_exc:
        last_exc: Exception = first_exc

    # 2. Extract from fenced ```json ... ``` or ``` ... ``` blocks anywhere in the response
    for block in re.findall(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.DOTALL | re.IGNORECASE):
        candidate = block.strip()
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_exc = exc

    # 3. Fallback: scan for the first valid JSON object or array using JSONDecoder
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(cleaned):
        if ch in "{[":
            try:
                parsed, _ = decoder.raw_decode(cleaned[idx:])
                if isinstance(parsed, (dict, list)):
                    return parsed
            except json.JSONDecodeError as exc:
                last_exc = exc

    raise LLMError(f'LLM did not return valid JSON: {last_exc}') from last_exc
