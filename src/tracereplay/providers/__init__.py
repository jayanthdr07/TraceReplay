"""Provider adapters and patching mechanisms for TraceReplay."""

from __future__ import annotations

from tracereplay.providers.anthropic import (
    AnthropicAdapter,
    AnthropicMessageResponse,
    AnthropicTextBlock,
    AnthropicToolUseBlock,
    AnthropicUsage,
)
from tracereplay.providers.base import BaseProviderAdapter
from tracereplay.providers.gemini import (
    GeminiAdapter,
    GeminiCandidate,
    GeminiContent,
    GeminiGenerateContentResponse,
    GeminiPart,
    GeminiUsageMetadata,
)
from tracereplay.providers.groq import DeepSeekAdapter, GroqAdapter, OllamaAdapter
from tracereplay.providers.openai import (
    ChatCompletionResponse,
    ChoiceObject,
    FunctionCallObject,
    MessageObject,
    OpenAIAdapter,
    ToolCallObject,
    UsageObject,
)
from tracereplay.providers.patcher import PatchHandle, patch, unpatch

__all__ = [
    # Base
    "BaseProviderAdapter",
    "PatchHandle",
    "patch",
    "unpatch",
    # OpenAI & Groq & DeepSeek & Ollama
    "OpenAIAdapter",
    "GroqAdapter",
    "DeepSeekAdapter",
    "OllamaAdapter",
    "ChatCompletionResponse",
    "ChoiceObject",
    "FunctionCallObject",
    "MessageObject",
    "ToolCallObject",
    "UsageObject",
    # Anthropic Claude
    "AnthropicAdapter",
    "AnthropicMessageResponse",
    "AnthropicTextBlock",
    "AnthropicToolUseBlock",
    "AnthropicUsage",
    # Google Gemini
    "GeminiAdapter",
    "GeminiGenerateContentResponse",
    "GeminiCandidate",
    "GeminiContent",
    "GeminiPart",
    "GeminiUsageMetadata",
]
