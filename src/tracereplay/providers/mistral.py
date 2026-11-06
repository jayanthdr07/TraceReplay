"""Mistral AI provider adapter and response reconstruction engine."""

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
from tracereplay.providers.openai import (
    ChoiceObject,
    FunctionCallObject,
    MessageObject,
    ToolCallObject,
    UsageObject,
)


class MistralChatCompletionResponse(BaseModel):
    """Native-compatible Mistral ChatCompletion response object."""

    model_config = ConfigDict(frozen=True)

    id: str = "mistral_cmpl_replayed"
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "mistral-large-latest"
    choices: list[ChoiceObject] = Field(default_factory=list)
    usage: UsageObject = Field(default_factory=UsageObject)

    def to_dict(self) -> dict[str, Any]:
        """Convenience method returning response as dictionary."""
        return self.model_dump()


class MistralAdapter(BaseProviderAdapter):
    """Adapter for intercepting and replaying Mistral AI chat completions."""

    provider_name: str = "mistral"

    def before_request(self, *args: Any, **kwargs: Any) -> RequestPayload:
        """Extract and normalize Mistral request parameters into RequestPayload."""
        model = str(kwargs.get("model", "mistral-large-latest"))
        raw_messages = kwargs.get("messages", [])
        tools = kwargs.get("tools")
        temperature = kwargs.get("temperature")
        max_tokens = kwargs.get("max_tokens")

        normalized_messages: list[dict[str, Any]] = []
        for msg in raw_messages:
            if isinstance(msg, dict):
                normalized_messages.append(msg)
            elif hasattr(msg, "role") and hasattr(msg, "content"):
                msg_dict: dict[str, Any] = {
                    "role": msg.role,
                    "content": msg.content,
                }
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    msg_dict["tool_calls"] = msg.tool_calls
                normalized_messages.append(msg_dict)
            else:
                normalized_messages.append({"role": "user", "content": str(msg)})

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
            messages=normalized_messages,
            parameters=parameters,
            tools=tools,
        )

    def after_response(self, raw_response: Any) -> ResponsePayload:
        """Extract ResponsePayload from a raw Mistral completion response."""
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
            raw_finish_reason = getattr(first_choice, "finish_reason", "stop") or "stop"
            finish_reason = raw_finish_reason if isinstance(raw_finish_reason, str) else "stop"
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
    ) -> MistralChatCompletionResponse:
        """Reconstruct a native-compatible Mistral response from ResponsePayload."""
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

        return MistralChatCompletionResponse(
            model=request.model,
            choices=[choice],
            usage=usage,
        )
