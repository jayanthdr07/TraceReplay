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
    GeminiFunctionCall,
    GeminiGenerateContentResponse,
    GeminiPart,
    GeminiUsageMetadata,
)
from tracereplay.providers.generic import GenericOpenAIAdapter
from tracereplay.providers.groq import DeepSeekAdapter, GroqAdapter, OllamaAdapter
from tracereplay.providers.mistral import (
    MistralAdapter,
    MistralChatCompletionResponse,
)
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
    # OpenAI & Groq & DeepSeek & Ollama & Generic
    "OpenAIAdapter",
    "GroqAdapter",
    "DeepSeekAdapter",
    "OllamaAdapter",
    "GenericOpenAIAdapter",
    "ChatCompletionResponse",
    "ChoiceObject",
    "FunctionCallObject",
    "MessageObject",
    "ToolCallObject",
    "UsageObject",
    # Mistral AI
    "MistralAdapter",
    "MistralChatCompletionResponse",
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
    "GeminiFunctionCall",
    "GeminiPart",
    "GeminiUsageMetadata",
]
