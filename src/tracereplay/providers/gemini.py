"""Google Gemini provider adapter and response reconstruction engine."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tracereplay.models import (
    OperationType,
    RequestPayload,
    ResponsePayload,
    TokenUsage,
)
from tracereplay.providers.base import BaseProviderAdapter


class GeminiPart(BaseModel):
    """Part representation of Gemini content."""

    model_config = ConfigDict(frozen=True)

    text: str | None = None


class GeminiContent(BaseModel):
    """Content representation in Gemini candidate."""

    model_config = ConfigDict(frozen=True)

    parts: list[GeminiPart] = Field(default_factory=list)
    role: str = "model"


class GeminiCandidate(BaseModel):
    """Candidate representation in Gemini response."""

    model_config = ConfigDict(frozen=True)

    content: GeminiContent = Field(default_factory=GeminiContent)
    finish_reason: str = "STOP"


class GeminiUsageMetadata(BaseModel):
    """Usage metadata representation in Gemini response."""

    model_config = ConfigDict(frozen=True)

    prompt_token_count: int = 0
    candidates_token_count: int = 0
    total_token_count: int = 0


class GeminiGenerateContentResponse(BaseModel):
    """Native-compatible Google Gemini generate_content response object."""

    model_config = ConfigDict(frozen=True)

    candidates: list[GeminiCandidate] = Field(default_factory=list)
    usage_metadata: GeminiUsageMetadata = Field(default_factory=GeminiUsageMetadata)

    @property
    def text(self) -> str:
        """Convenience property matching official Gemini SDK response.text."""
        if self.candidates and self.candidates[0].content.parts:
            return self.candidates[0].content.parts[0].text or ""
        return ""

    def to_dict(self) -> dict[str, Any]:
        """Convenience method returning payload as dictionary."""
        return self.model_dump()


class GeminiAdapter(BaseProviderAdapter):
    """Adapter for intercepting and replaying Google Gemini generate_content calls."""

    provider_name: str = "gemini"

    def before_request(self, *args: Any, **kwargs: Any) -> RequestPayload:
        """Extract and normalize request parameters into RequestPayload."""
        model = str(kwargs.get("model", "gemini-1.5-pro"))
        contents = kwargs.get("contents") or (args[0] if args else [])

        messages: list[dict[str, Any]] = []
        prompt_text: str | None = None

        if isinstance(contents, str):
            prompt_text = contents
            messages.append({"role": "user", "content": contents})
        elif isinstance(contents, list):
            for c in contents:
                if isinstance(c, str):
                    messages.append({"role": "user", "content": c})
                elif isinstance(c, dict):
                    messages.append(c)

        parameters = {k: v for k, v in kwargs.items() if k not in {"model", "contents"}}

        return RequestPayload(
            provider=self.provider_name,
            model=model,
            operation=OperationType.CHAT_COMPLETION,
            prompt=prompt_text,
            messages=messages,
            parameters=parameters,
        )

    def after_response(self, raw_response: Any) -> ResponsePayload:
        """Extract ResponsePayload from a raw Gemini generate_content response."""
        if isinstance(raw_response, dict):
            text = raw_response.get("text", "")
            usage_data = raw_response.get("usage_metadata", {})
        else:
            text = getattr(raw_response, "text", "")
            usage_data = getattr(raw_response, "usage_metadata", None)

        if isinstance(usage_data, dict):
            prompt_t = usage_data.get("prompt_token_count", 0)
            cand_t = usage_data.get("candidates_token_count", 0)
            tot_t = usage_data.get("total_token_count", prompt_t + cand_t)
        elif usage_data is not None:
            prompt_t = getattr(usage_data, "prompt_token_count", 0)
            cand_t = getattr(usage_data, "candidates_token_count", 0)
            tot_t = getattr(usage_data, "total_token_count", prompt_t + cand_t)
        else:
            prompt_t, cand_t, tot_t = 0, 0, 0

        usage = TokenUsage(
            prompt_tokens=prompt_t,
            completion_tokens=cand_t,
            total_tokens=tot_t,
        )

        return ResponsePayload(
            content=text,
            finish_reason="STOP",
            usage=usage,
        )

    def build_replayed_response(
        self, response_payload: ResponsePayload, request: RequestPayload
    ) -> GeminiGenerateContentResponse:
        """Reconstruct a native-compatible GeminiGenerateContentResponse from ResponsePayload."""
        part = GeminiPart(text=response_payload.content)
        content = GeminiContent(parts=[part], role="model")
        candidate = GeminiCandidate(
            content=content,
            finish_reason=response_payload.finish_reason or "STOP",
        )
        usage = GeminiUsageMetadata(
            prompt_token_count=response_payload.usage.prompt_tokens,
            candidates_token_count=response_payload.usage.completion_tokens,
            total_token_count=response_payload.usage.total_tokens,
        )
        return GeminiGenerateContentResponse(
            candidates=[candidate],
            usage_metadata=usage,
        )

