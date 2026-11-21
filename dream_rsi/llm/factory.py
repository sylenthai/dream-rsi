from __future__ import annotations

import os
from .providers import AnthropicClient, OllamaClient, OpenAICompatibleClient, GeminiClient


def create_llm(provider: str, model: str | None = None):
    provider = provider.lower().strip()
    if provider == "ollama":
        return OllamaClient(model=model or os.getenv("DREAM_RSI_MODEL", "qwen3.5:9b"),
                            base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    if provider in {"openai", "openai-compatible"}:
        return OpenAICompatibleClient(model=model or os.getenv("DREAM_RSI_MODEL", "gpt-5.6-mini"),
                                      base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    if provider == "gemini":
        return GeminiClient(model=model or os.getenv("DREAM_RSI_MODEL", "gemini-2.5-flash"))
    if provider in {"anthropic", "claude"}:
        return AnthropicClient(model=model or os.getenv("DREAM_RSI_MODEL", "claude-3-5-sonnet-latest"),
                               base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"))
    if provider == "deepseek":
        return OpenAICompatibleClient(
            model=model or os.getenv("DREAM_RSI_MODEL", "deepseek-chat"),
            api_key=os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        )
    if provider == "groq":
        return OpenAICompatibleClient(
            model=model or os.getenv("DREAM_RSI_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        )
    if provider == "openrouter":
        return OpenAICompatibleClient(
            model=model or os.getenv("DREAM_RSI_MODEL", "openai/gpt-4o-mini"),
            api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        )
    raise ValueError(f"unknown LLM provider: {provider}")


# Backwards-compatible alias kept within the current release API.
build_llm = create_llm
