"""Groq, DeepSeek, and Ollama provider adapters (OpenAI API compatible)."""

from __future__ import annotations

from tracereplay.providers.openai import OpenAIAdapter


class GroqAdapter(OpenAIAdapter):
    """Adapter for Groq LPU inference (OpenAI SDK compatible)."""

    provider_name: str = "groq"


class DeepSeekAdapter(OpenAIAdapter):
    """Adapter for DeepSeek API (OpenAI SDK compatible)."""

    provider_name: str = "deepseek"


class OllamaAdapter(OpenAIAdapter):
    """Adapter for Ollama local models (OpenAI SDK compatible)."""

    provider_name: str = "ollama"
