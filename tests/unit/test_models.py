"""Unit tests for Pydantic data models and schemas."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from tracereplay.models import (
    Interaction,
    OperationType,
    ReplayMode,
    RequestPayload,
    ResponsePayload,
    SessionRecord,
    TokenUsage,
    ToolCallRecord,
)


def test_replay_mode_values() -> None:
    """Verify all expected enum values for ReplayMode."""
    assert ReplayMode.RECORD.value == "record"
    assert ReplayMode.REPLAY.value == "replay"
    assert ReplayMode.AUTO.value == "auto"
    assert ReplayMode.PASSTHROUGH.value == "passthrough"


def test_token_usage_creation_and_defaults() -> None:
    """Verify default values and non-negative constraints on TokenUsage."""
    usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    assert usage.prompt_tokens == 100
    assert usage.completion_tokens == 50
    assert usage.total_tokens == 150
    assert usage.estimated_cost_usd is None

    # Negative tokens should raise ValidationError (tested via model_validate)
    with pytest.raises(ValidationError):
        TokenUsage.model_validate({"prompt_tokens": -1})


def test_tool_call_record() -> None:
    """Verify ToolCallRecord serialization and attributes."""
    tool = ToolCallRecord(
        function_name="get_weather",
        arguments={"city": "San Francisco", "unit": "celsius"},
        result={"temperature": 18},
        error=None,
    )
    assert tool.function_name == "get_weather"
    assert tool.arguments["city"] == "San Francisco"
    assert tool.result == {"temperature": 18}
    assert tool.id.startswith("call_")


def test_request_payload_helpers() -> None:
    """Verify get_prompt_text and get_tool_names helpers on RequestPayload."""
    req_messages = RequestPayload(
        provider="anthropic",
        model="claude-3-5-sonnet",
        messages=[
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "What is the capital of France?"},
        ],
        tools=[
            {"type": "function", "function": {"name": "lookup_capital"}},
            {"name": "calculator"},
        ],
    )
    assert req_messages.get_prompt_text() == "What is the capital of France?"
    assert req_messages.get_tool_names() == ["lookup_capital", "calculator"]

    # Test prompt fallback
    req_prompt = RequestPayload(provider="openai", model="gpt-4o", prompt="Hello LLM")
    assert req_prompt.get_prompt_text() == "Hello LLM"


def test_response_streaming_payload() -> None:
    """Verify streaming chunk storage in ResponsePayload."""
    chunks = [
        {"id": "c1", "delta": {"content": "Hello"}},
        {"id": "c2", "delta": {"content": " world"}},
    ]
    res = ResponsePayload(
        content="Hello world",
        is_streaming=True,
        stream_chunks=chunks,
    )
    assert res.is_streaming is True
    assert res.stream_chunks is not None
    assert len(res.stream_chunks) == 2


def test_session_record_helpers_and_serialization() -> None:
    """Verify complete end-to-end serialization and session helper methods."""
    req = RequestPayload(
        provider="openai",
        model="gpt-4o",
        operation=OperationType.CHAT_COMPLETION,
        messages=[{"role": "user", "content": "What is 2+2?"}],
        parameters={"temperature": 0.0},
    )
    tool = ToolCallRecord(function_name="calculate", arguments={"expr": "2+2"}, result="4")
    res = ResponsePayload(
        content="2 + 2 = 4",
        finish_reason="stop",
        tool_calls=[tool],
        usage=TokenUsage(prompt_tokens=10, completion_tokens=7, total_tokens=17),
    )
    interaction = Interaction(
        session_id="sess_test_123",
        index=0,
        duration_ms=125.4,
        request=req,
        response=res,
    )
    session = SessionRecord(
        name="test_math_flow",
        test_name="test_addition",
        interactions=[interaction],
    )

    # Test session helper properties
    assert session.total_interactions == 1
    assert session.total_tokens == 17
    assert session.total_duration_ms == 125.4
    assert session.schema_version == "1.0"
    assert session.get_interaction(0) == interaction
    assert session.get_interaction(999) is None
    assert len(session.get_tool_calls()) == 1
    assert session.get_tool_calls()[0].function_name == "calculate"

    # Test find_interactions
    assert len(session.find_interactions(provider="openai")) == 1
    assert len(session.find_interactions(provider="anthropic")) == 0
    assert len(session.find_interactions(model="gpt-4o")) == 1

    # Verify JSON roundtrip
    json_str = session.model_dump_json(indent=2)
    data = json.loads(json_str)
    assert data["name"] == "test_math_flow"
    assert data["interactions"][0]["request"]["model"] == "gpt-4o"
    assert data["interactions"][0]["response"]["content"] == "2 + 2 = 4"

    # Deserialization test
    loaded_session = SessionRecord.model_validate(data)
    assert loaded_session.session_id == session.session_id
    assert loaded_session.interactions[0].duration_ms == 125.4
    assert isinstance(loaded_session.created_at, datetime)


def test_model_immutability() -> None:
    """Verify that models are immutable (frozen) to prevent accidental mutation."""
    req = RequestPayload(provider="openai", model="gpt-4o")
    with pytest.raises(ValidationError):
        # Mutating frozen model must raise ValidationError at runtime
        req.__setattr__("model", "gpt-3.5")
