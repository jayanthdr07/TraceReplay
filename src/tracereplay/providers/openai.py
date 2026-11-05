"""OpenAI provider adapter and response reconstruction engine."""

from __future__ import annotations

import json
import time
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


class FunctionCallObject(BaseModel):
    """Native OpenAI function call object representation."""

    model_config = ConfigDict(frozen=True)

    name: str
    arguments: str


class ToolCallObject(BaseModel):
    """Native OpenAI tool call representation."""

    model_config = ConfigDict(frozen=True)

    id: str
    type: str = "function"
    function: FunctionCallObject


class MessageObject(BaseModel):
    """Native OpenAI assistant message representation."""

    model_config = ConfigDict(frozen=True)

    role: str = "assistant"
    content: str | None = None
    tool_calls: list[ToolCallObject] | None = None


class ChoiceObject(BaseModel):
    """Native OpenAI completion choice representation."""

    model_config = ConfigDict(frozen=True)

    index: int = 0
    message: MessageObject
    finish_reason: str = "stop"


class UsageObject(BaseModel):
    """Native OpenAI token usage representation."""

    model_config = ConfigDict(frozen=True)

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """Native-compatible OpenAI ChatCompletion response object."""

    model_config = ConfigDict(frozen=True)

    id: str = "chatcmpl_replayed"
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "gpt-4o"
    choices: list[ChoiceObject] = Field(default_factory=list)
    usage: UsageObject = Field(default_factory=UsageObject)
    system_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convenience method returning response as a dictionary."""
        return self.model_dump()


class OpenAIAdapter(BaseProviderAdapter):
    """Adapter for intercepting and replaying OpenAI Chat Completions."""

    provider_name: str = "openai"

    def before_request(self, *args: Any, **kwargs: Any) -> RequestPayload:
        """Extract and normalize request parameters into RequestPayload."""
        model = str(kwargs.get("model", "gpt-4o"))
        messages = list(kwargs.get("messages", []))
        tools = kwargs.get("tools")
        temperature = kwargs.get("temperature")
        max_tokens = kwargs.get("max_tokens")

        parameters: dict[str, Any] = {}
        if temperature is not None:
            parameters["temperature"] = temperature
        if max_tokens is not None:
            parameters["max_tokens"] = max_tokens

        # Collect any remaining non-standard parameters
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
        """Extract ResponsePayload from a raw OpenAI ChatCompletion response."""
        if isinstance(raw_response, dict):
            choices_data = raw_response.get("choices", [{}])
            first_choice = choices_data[0] if choices_data else {}
            msg_data = first_choice.get("message", {})
            content = msg_data.get("content")
            finish_reason = first_choice.get("finish_reason", "stop")
            tool_calls_data = msg_data.get("tool_calls", [])
            usage_data = raw_response.get("usage", {})
        else:
            first_choice = (
                raw_response.choices[0] if getattr(raw_response, "choices", None) else None
            )
            msg_data = getattr(first_choice, "message", None) if first_choice else None
            content = getattr(msg_data, "content", None)
            finish_reason = getattr(first_choice, "finish_reason", "stop") or "stop"
            tool_calls_data = getattr(msg_data, "tool_calls", None) or []
            usage_data = getattr(raw_response, "usage", None)

        tool_calls: list[ToolCallRecord] = []
        for tc in tool_calls_data:
            if isinstance(tc, dict):
                tc_id = tc.get("id", "")
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments", "{}")
            else:
                tc_id = getattr(tc, "id", "")
                fn = getattr(tc, "function", None)
                name = getattr(fn, "name", "") if fn else ""
                args = getattr(fn, "arguments", "{}") if fn else "{}"

            parsed_args: dict[str, Any] = {}
            if isinstance(args, str):
                raw_args = args
                try:
                    parsed_args = json.loads(args) if args else {}
                except Exception:
                    parsed_args = {}
            elif isinstance(args, dict):
                parsed_args = args
                raw_args = json.dumps(args)
            else:
                raw_args = "{}"

            tool_calls.append(
                ToolCallRecord(
                    id=tc_id,
                    type="function",
                    function_name=name,
                    arguments=parsed_args,
                    raw_arguments=raw_args,
                )
            )

        if isinstance(usage_data, dict):
            usage = TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )
        elif usage_data is not None:
            usage = TokenUsage(
                prompt_tokens=getattr(usage_data, "prompt_tokens", 0),
                completion_tokens=getattr(usage_data, "completion_tokens", 0),
                total_tokens=getattr(usage_data, "total_tokens", 0),
            )
        else:
            usage = TokenUsage()

        return ResponsePayload(
            content=content,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            usage=usage,
        )

    def build_replayed_response(
        self, response_payload: ResponsePayload, request: RequestPayload
    ) -> ChatCompletionResponse:
        """Reconstruct a native-compatible ChatCompletionResponse from ResponsePayload."""
        tool_call_objs: list[ToolCallObject] | None = None
        if response_payload.tool_calls:
            tool_call_objs = [
                ToolCallObject(
                    id=tc.id,
                    type="function",
                    function=FunctionCallObject(
                        name=tc.function_name,
                        arguments=tc.raw_arguments or json.dumps(tc.arguments),
                    ),
                )
                for tc in response_payload.tool_calls
            ]

        message = MessageObject(
            role="assistant",
            content=response_payload.content,
            tool_calls=tool_call_objs,
        )

        choice = ChoiceObject(
            index=0,
            message=message,
            finish_reason=response_payload.finish_reason or "stop",
        )

        usage = UsageObject(
            prompt_tokens=response_payload.usage.prompt_tokens,
            completion_tokens=response_payload.usage.completion_tokens,
            total_tokens=response_payload.usage.total_tokens,
        )

        return ChatCompletionResponse(
            model=request.model,
            choices=[choice],
            usage=usage,
        )
