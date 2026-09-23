from __future__ import annotations

import os
from .providers import OllamaClient, OpenAICompatibleClient, GeminiClient


def create_llm(provider: str, model: str | None = None):
    provider = provider.lower()
    if provider == "ollama":
        return OllamaClient(model=model or os.getenv("DREAM_RSI_MODEL", "qwen3.5:9b"),
                            base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    if provider in {"openai", "openai-compatible"}:
        return OpenAICompatibleClient(model=model or os.getenv("DREAM_RSI_MODEL", "gpt-5.6-mini"),
                                      base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    if provider == "gemini":
        return GeminiClient(model=model or os.getenv("DREAM_RSI_MODEL", "gemini-2.5-flash"))
    raise ValueError(f"unknown LLM provider: {provider}")


# Backwards-compatible alias kept within the current release API.
build_llm = create_llm
