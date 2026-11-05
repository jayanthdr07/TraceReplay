"""Anthropic (Claude) provider adapter and response reconstruction engine."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tracereplay.models import (
    OperationType,
    RequestPayload,
    ResponsePayload,
    TokenUsage,
    ToolCallRecord,
)
from tracereplay.providers.base import BaseProviderAdapter


class AnthropicTextBlock(BaseModel):
    """Native Anthropic text content block."""

    model_config = ConfigDict(frozen=True)

    type: str = "text"
    text: str


class AnthropicToolUseBlock(BaseModel):
    """Native Anthropic tool use content block."""

    model_config = ConfigDict(frozen=True)

    type: str = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class AnthropicUsage(BaseModel):
    """Native Anthropic token usage metadata."""

    model_config = ConfigDict(frozen=True)

    input_tokens: int = 0
    output_tokens: int = 0


class AnthropicMessageResponse(BaseModel):
    """Native-compatible Anthropic Message response object."""

    model_config = ConfigDict(frozen=True)

    id: str = "msg_replayed"
    type: str = "message"
    role: str = "assistant"
    model: str = "claude-3-5-sonnet"
    content: list[AnthropicTextBlock | AnthropicToolUseBlock] = Field(default_factory=list)
    stop_reason: str = "end_turn"
    usage: AnthropicUsage = Field(default_factory=AnthropicUsage)

    def to_dict(self) -> dict[str, Any]:
        """Convenience method returning message payload as a dictionary."""
        return self.model_dump()


class AnthropicAdapter(BaseProviderAdapter):
    """Adapter for intercepting and replaying Anthropic Claude Messages."""

    provider_name: str = "anthropic"

    def before_request(self, *args: Any, **kwargs: Any) -> RequestPayload:
        """Extract and normalize request parameters into RequestPayload."""
        model = str(kwargs.get("model", "claude-3-5-sonnet"))
        messages = list(kwargs.get("messages", []))
        tools = kwargs.get("tools")
        temperature = kwargs.get("temperature")
        max_tokens = kwargs.get("max_tokens")

        parameters: dict[str, Any] = {}
        if temperature is not None:
            parameters["temperature"] = temperature
        if max_tokens is not None:
            parameters["max_tokens"] = max_tokens

        for k, v in kwargs.items():
            if k not in {"model", "messages", "tools", "temperature", "max_tokens"}:
                parameters[k] = v

        return RequestPayload(
            provider=self.provider_name,
            model=model,
            operation=OperationType.CHAT_COMPLETION,
            messages=messages,
            parameters=parameters,
            tools=tools,
        )

    def after_response(self, raw_response: Any) -> ResponsePayload:
        """Extract ResponsePayload from a raw Anthropic Message response."""
        if isinstance(raw_response, dict):
            content_blocks = raw_response.get("content", [])
            stop_reason = raw_response.get("stop_reason", "end_turn")
            usage_data = raw_response.get("usage", {})
        else:
            content_blocks = getattr(raw_response, "content", [])
            stop_reason = getattr(raw_response, "stop_reason", "end_turn")
            usage_data = getattr(raw_response, "usage", None)

        text_parts: list[str] = []
        tool_calls: list[ToolCallRecord] = []

        for block in content_blocks:
            if isinstance(block, dict):
                b_type = block.get("type", "")
                if b_type == "text":
                    text_parts.append(block.get("text", ""))
                elif b_type == "tool_use":
                    tc_id = block.get("id", "")
                    name = block.get("name", "")
                    tc_input = block.get("input", {})
                    tool_calls.append(
                        ToolCallRecord(
                            id=tc_id,
                            type="function",
                            function_name=name,
                            arguments=tc_input,
                            raw_arguments=json.dumps(tc_input),
                        )
                    )
            else:
                b_type = getattr(block, "type", "")
                if b_type == "text":
                    text_parts.append(getattr(block, "text", ""))
                elif b_type == "tool_use":
                    tc_id = getattr(block, "id", "")
                    name = getattr(block, "name", "")
                    tc_input = getattr(block, "input", {})
                    tool_calls.append(
                        ToolCallRecord(
                            id=tc_id,
                            type="function",
                            function_name=name,
                            arguments=tc_input,
                            raw_arguments=json.dumps(tc_input),
                        )
                    )

        full_text = "".join(text_parts) if text_parts else None

        if isinstance(usage_data, dict):
            inp = usage_data.get("input_tokens", 0)
            out = usage_data.get("output_tokens", 0)
        elif usage_data is not None:
            inp = getattr(usage_data, "input_tokens", 0)
            out = getattr(usage_data, "output_tokens", 0)
        else:
            inp = 0
            out = 0

        usage = TokenUsage(
            prompt_tokens=inp,
            completion_tokens=out,
            total_tokens=inp + out,
        )

        return ResponsePayload(
            content=full_text,
            finish_reason=stop_reason,
            tool_calls=tool_calls,
            usage=usage,
        )

    def build_replayed_response(
        self, response_payload: ResponsePayload, request: RequestPayload
    ) -> AnthropicMessageResponse:
        """Reconstruct a native-compatible AnthropicMessageResponse from ResponsePayload."""
        blocks: list[AnthropicTextBlock | AnthropicToolUseBlock] = []
        if response_payload.content:
            blocks.append(AnthropicTextBlock(text=response_payload.content))

        for tc in response_payload.tool_calls:
            blocks.append(
                AnthropicToolUseBlock(
                    id=tc.id,
                    name=tc.function_name,
                    input=tc.arguments,
                )
            )

        usage = AnthropicUsage(
            input_tokens=response_payload.usage.prompt_tokens,
            output_tokens=response_payload.usage.completion_tokens,
        )

        return AnthropicMessageResponse(
            model=request.model,
            content=blocks,
            stop_reason=response_payload.finish_reason or "end_turn",
            usage=usage,
        )

