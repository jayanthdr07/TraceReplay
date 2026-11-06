"""Generic OpenAI-compatible provider adapter with parameter sanitization."""

from __future__ import annotations

from typing import Any

from tracereplay.models import OperationType, RequestPayload
from tracereplay.providers.openai import OpenAIAdapter

# Parameters injected by local inference engines that should be stripped or normalized
# to prevent environment-specific fixture mismatches
LOCAL_ENGINE_EPHEMERAL_PARAMS: frozenset[str] = frozenset({
    "keep_alive",
    "num_ctx",
    "repeat_penalty",
    "repetition_penalty",
    "top_k",
    "seed",
    "options",
    "extra_body",
    "model_kwargs",
})


class GenericOpenAIAdapter(OpenAIAdapter):
    """Universal adapter for local & self-hosted OpenAI-compatible inference servers:
    - Ollama (http://localhost:11434/v1)
    - vLLM (http://localhost:8000/v1)
    - LM Studio (http://localhost:1234/v1)
    - LocalAI (http://localhost:8080/v1)
    - Together AI, OpenRouter, Anyscale
    """

    provider_name: str = "generic"

    def __init__(self, provider_alias: str = "generic") -> None:
        self.provider_name = provider_alias

    def before_request(self, *args: Any, **kwargs: Any) -> RequestPayload:
        """Extract and normalize request parameters, filtering out engine-specific quirks."""
        model = str(kwargs.get("model", "default-model"))
        messages = list(kwargs.get("messages", []))
        tools = kwargs.get("tools")
        temperature = kwargs.get("temperature")
        max_tokens = kwargs.get("max_tokens")

        parameters: dict[str, Any] = {}
        if temperature is not None:
            parameters["temperature"] = temperature
        if max_tokens is not None:
            parameters["max_tokens"] = max_tokens

        # Collect standard parameters, ignoring ephemeral engine-specific flags
        for k, v in kwargs.items():
            if (
                k not in {"model", "messages", "tools", "temperature", "max_tokens"}
                and k not in LOCAL_ENGINE_EPHEMERAL_PARAMS
            ):
                parameters[k] = v

        return RequestPayload(
            provider=self.provider_name,
            model=model,
            operation=OperationType.CHAT_COMPLETION,
            messages=messages,
            parameters=parameters,
            tools=tools,
        )
