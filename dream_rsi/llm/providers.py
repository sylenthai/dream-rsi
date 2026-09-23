from __future__ import annotations
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any
from .client import LLMError, LLMResponse


def _post(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float, retries: int) -> dict[str, Any]:
    body = json.dumps(payload).encode('utf-8')
    last: Exception | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=body, headers={**headers, 'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode('utf-8')
                return json.loads(raw)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            if attempt < retries:
                time.sleep(min(2 ** attempt, 4))
    raise LLMError(f'LLM request failed after {retries + 1} attempts: {last}')


class OllamaClient:
    def __init__(self, model: str = 'qwen3.5:9b', base_url: str = 'http://127.0.0.1:11434',
                 timeout: float = 180.0, retries: int = 2):
        self.model, self.base_url, self.timeout, self.retries = model, base_url.rstrip('/'), timeout, retries

    def generate(self, messages, *, temperature=0.2, max_tokens=2048, response_format=None):
        prompt = '\n\n'.join(f"{m['role'].upper()}: {m['content']}" for m in messages)
        payload = {
            'model': self.model,
            'prompt': prompt,
            'stream': False,
            'options': {'temperature': temperature, 'num_predict': max_tokens},
        }
        # Ollama's format=json is useful for policy JSON, while leaving normal generation unconstrained.
        if response_format == 'json':
            payload['format'] = 'json'
        data = _post(f'{self.base_url}/api/generate', payload, {}, self.timeout, self.retries)
        return LLMResponse(data.get('response', ''), self.model, raw=data)


class OpenAICompatibleClient:
    def __init__(self, model: str, api_key: str | None = None,
                 base_url: str = 'https://api.openai.com/v1', timeout: float = 180.0, retries: int = 2):
        self.model, self.api_key = model, api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise LLMError('OPENAI_API_KEY is not set')
        self.base_url, self.timeout, self.retries = base_url.rstrip('/'), timeout, retries

    def generate(self, messages, *, temperature=0.2, max_tokens=2048, response_format=None):
        payload = {'model': self.model, 'messages': messages, 'temperature': temperature, 'max_tokens': max_tokens}
        if response_format == 'json':
            payload['response_format'] = {'type': 'json_object'}
        data = _post(f'{self.base_url}/chat/completions', payload,
                     {'Authorization': f'Bearer {self.api_key}'}, self.timeout, self.retries)
        choice = data.get('choices', [{}])[0]
        message = choice.get('message', {})
        usage = data.get('usage', {}) or {}
        return LLMResponse(message.get('content', ''), self.model,
                           usage.get('prompt_tokens'), usage.get('completion_tokens'), data)


class GeminiClient:
    def __init__(self, model: str, api_key: str | None = None,
                 base_url: str = 'https://generativelanguage.googleapis.com/v1beta', timeout: float = 180.0, retries: int = 2):
        self.model = model
        self.api_key = api_key or os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise LLMError('GEMINI_API_KEY or GOOGLE_API_KEY is not set')
        self.base_url, self.timeout, self.retries = base_url.rstrip('/'), timeout, retries

    def generate(self, messages, *, temperature=0.2, max_tokens=2048, response_format=None):
        contents = []
        for m in messages:
            role = 'model' if m['role'] == 'assistant' else 'user'
            contents.append({'role': role, 'parts': [{'text': m['content']}]})
        payload = {
            'contents': contents,
            'generationConfig': {'temperature': temperature, 'maxOutputTokens': max_tokens},
        }
        if response_format == 'json':
            payload['generationConfig']['responseMimeType'] = 'application/json'
        url = f'{self.base_url}/models/{self.model}:generateContent'
        headers = {'x-goog-api-key': self.api_key}
        data = _post(url, payload, headers, self.timeout, self.retries)
        candidates = data.get('candidates', [])
        text = ''
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            text = ''.join(p.get('text', '') for p in parts)
        usage = data.get('usageMetadata', {}) or {}
        return LLMResponse(text, self.model, usage.get('promptTokenCount'), usage.get('candidatesTokenCount'), data)
