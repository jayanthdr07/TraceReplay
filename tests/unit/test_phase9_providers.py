"""Unit tests for Phase 9 provider expansion.

Covers Mistral, Generic, Anthropic tools, and Gemini function calls.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from tracereplay.config import TraceReplayConfig
from tracereplay.core.session import session
from tracereplay.models import ReplayMode
from tracereplay.providers.anthropic import AnthropicToolUseBlock
from tracereplay.providers.generic import GenericOpenAIAdapter
from tracereplay.providers.mistral import MistralAdapter, MistralChatCompletionResponse
from tracereplay.providers.patcher import _resolve_adapter, patch, unpatch


class MockMistralMessage:
    def __init__(
        self, role: str = "assistant", content: str = "", tool_calls: list[Any] | None = None
    ) -> None:
        self.role = role
        self.content = content
        self.tool_calls = tool_calls or []


class MockMistralChoice:
    def __init__(self, message: MockMistralMessage, finish_reason: str = "stop") -> None:
        self.message = message
        self.finish_reason = finish_reason
        self.index = 0


class MockMistralUsage:
    def __init__(self, prompt: int = 10, completion: int = 5) -> None:
        self.prompt_tokens = prompt
        self.completion_tokens = completion
        self.total_tokens = prompt + completion


class MockMistralResponse:
    def __init__(
        self,
        content: str = "Mistral response",
        tool_calls: list[Any] | None = None,
        model: str = "mistral-large-latest",
    ) -> None:
        self.id = "cmpl_mistral_test"
        self.model = model
        msg = MockMistralMessage(content=content, tool_calls=tool_calls)
        self.choices = [MockMistralChoice(msg)]
        self.usage = MockMistralUsage()


class MockMistralChat:
    def __init__(self) -> None:
        self.complete = MagicMock(return_value=MockMistralResponse("Real Mistral response"))
        self.complete_async = AsyncMock(
            return_value=MockMistralResponse("Real async Mistral response")
        )


class MockMistralClient:
    def __init__(self) -> None:
        self.chat = MockMistralChat()


def test_mistral_sync_record_and_replay(tmp_path: Path) -> None:
    """Test sync recording and replay using MistralAdapter."""
    client = MockMistralClient()
    orig_mock = client.chat.complete
    patch(client, provider="mistral")

    cfg = TraceReplayConfig(fixtures_dir=tmp_path)

    # 1. Record Phase
    with session(name="mistral_test", mode=ReplayMode.RECORD, config=cfg):
        resp_rec = client.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": "What is Mistral?"}],
            temperature=0.7,
        )
        assert resp_rec.choices[0].message.content == "Real Mistral response"
        assert orig_mock.call_count == 1

    # Reset mock call count
    orig_mock.reset_mock()

    # 2. Replay Phase (Zero network calls)
    with session(name="mistral_test", mode=ReplayMode.REPLAY, config=cfg):
        resp_rep = client.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": "What is Mistral?"}],
            temperature=0.7,
        )
        assert isinstance(resp_rep, MistralChatCompletionResponse)
        assert resp_rep.choices[0].message.content == "Real Mistral response"
        assert resp_rep.usage.total_tokens == 15
        assert orig_mock.call_count == 0

    unpatch(client)


@pytest.mark.asyncio
async def test_mistral_async_record_and_replay(tmp_path: Path) -> None:
    """Test async recording and replay using MistralAdapter."""
    client = MockMistralClient()
    orig_async_mock = client.chat.complete_async
    patch(client, provider="mistral")

    cfg = TraceReplayConfig(fixtures_dir=tmp_path)

    # 1. Async Record Phase
    with session(name="mistral_async_test", mode=ReplayMode.RECORD, config=cfg):
        resp_rec = await client.chat.complete_async(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": "Async prompt"}],
        )
        assert resp_rec.choices[0].message.content == "Real async Mistral response"
        assert orig_async_mock.call_count == 1

    orig_async_mock.reset_mock()

    # 2. Async Replay Phase
    with session(name="mistral_async_test", mode=ReplayMode.REPLAY, config=cfg):
        resp_rep = await client.chat.complete_async(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": "Async prompt"}],
        )
        assert isinstance(resp_rep, MistralChatCompletionResponse)
        assert resp_rep.choices[0].message.content == "Real async Mistral response"
        assert orig_async_mock.call_count == 0

    unpatch(client)


def test_mistral_tool_calling_roundtrip(tmp_path: Path) -> None:
    """Test tool calling extraction and response reconstruction for Mistral."""
    client = MockMistralClient()
    mock_tool_call = {
        "id": "call_mistral_123",
        "type": "function",
        "function": {"name": "fetch_stock_price", "arguments": '{"ticker": "MSFT"}'},
    }
    client.chat.complete = MagicMock(
        return_value=MockMistralResponse(content="", tool_calls=[mock_tool_call])
    )
    patch(client, provider="mistral")

    cfg = TraceReplayConfig(fixtures_dir=tmp_path)

    # Record
    with session(name="mistral_tools", mode=ReplayMode.RECORD, config=cfg):
        resp_rec = client.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": "Stock price for MSFT?"}],
            tools=[{"type": "function", "function": {"name": "fetch_stock_price"}}],
        )
        assert len(resp_rec.choices[0].message.tool_calls) == 1

    # Replay
    with session(name="mistral_tools", mode=ReplayMode.REPLAY, config=cfg):
        resp_rep = client.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": "Stock price for MSFT?"}],
            tools=[{"type": "function", "function": {"name": "fetch_stock_price"}}],
        )
        assert isinstance(resp_rep, MistralChatCompletionResponse)
        assert resp_rep.choices[0].message.tool_calls is not None
        assert len(resp_rep.choices[0].message.tool_calls) == 1
        tc = resp_rep.choices[0].message.tool_calls[0]
        assert tc.id == "call_mistral_123"
        assert tc.function.name == "fetch_stock_price"
        assert "MSFT" in tc.function.arguments

    unpatch(client)


def test_generic_openai_adapter_parameter_cleaning() -> None:
    """Verify GenericOpenAIAdapter filters out local server options like num_ctx and keep_alive."""
    adapter = GenericOpenAIAdapter(provider_alias="ollama")

    req = adapter.before_request(
        model="llama3.2",
        messages=[{"role": "user", "content": "Hello"}],
        temperature=0.8,
        max_tokens=256,
        num_ctx=4096,
        keep_alive="5m",
        repetition_penalty=1.1,
        top_k=40,
        options={"num_ctx": 4096},
        extra_body={"guided_json": {}},
    )

    assert req.provider == "ollama"
    assert req.model == "llama3.2"
    assert req.parameters["temperature"] == 0.8
    assert req.parameters["max_tokens"] == 256
    # Ephemeral parameters must be filtered
    assert "num_ctx" not in req.parameters
    assert "keep_alive" not in req.parameters
    assert "repetition_penalty" not in req.parameters
    assert "top_k" not in req.parameters
    assert "options" not in req.parameters
    assert "extra_body" not in req.parameters


def test_anthropic_full_tool_use_roundtrip(tmp_path: Path) -> None:
    """Verify Anthropic tool_use content blocks are properly extracted and reconstructed."""

    class MockAnthropicMessages:
        def __init__(self) -> None:
            self.create = MagicMock()

    class MockAnthropicClient:
        def __init__(self) -> None:
            self.messages = MockAnthropicMessages()

    client = MockAnthropicClient()
    mock_raw_response = {
        "id": "msg_anthropic_123",
        "type": "message",
        "role": "assistant",
        "content": [
            {"type": "text", "text": "I will calculate this for you."},
            {
                "type": "tool_use",
                "id": "toolu_calc_01",
                "name": "calculator",
                "input": {"expression": "12 * 12"},
            },
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 25, "output_tokens": 18},
    }
    client.messages.create.return_value = mock_raw_response
    patch(client, provider="anthropic")

    cfg = TraceReplayConfig(fixtures_dir=tmp_path)

    # Record
    with session(name="anthropic_tools", mode=ReplayMode.RECORD, config=cfg):
        resp_rec = client.messages.create(
            model="claude-3-5-sonnet",
            messages=[{"role": "user", "content": "What is 12 * 12?"}],
            tools=[{"name": "calculator", "description": "Performs math"}],
            tool_choice={"type": "auto"},
        )
        assert len(resp_rec["content"]) == 2

    # Replay
    with session(name="anthropic_tools", mode=ReplayMode.REPLAY, config=cfg):
        resp_rep = client.messages.create(
            model="claude-3-5-sonnet",
            messages=[{"role": "user", "content": "What is 12 * 12?"}],
            tools=[{"name": "calculator", "description": "Performs math"}],
            tool_choice={"type": "auto"},
        )
        assert resp_rep.stop_reason == "tool_use"
        assert len(resp_rep.content) == 2
        assert resp_rep.content[0].type == "text"
        assert resp_rep.content[0].text == "I will calculate this for you."
        tool_block = resp_rep.content[1]
        assert isinstance(tool_block, AnthropicToolUseBlock)
        assert tool_block.name == "calculator"
        assert tool_block.input == {"expression": "12 * 12"}

    unpatch(client)


def test_gemini_function_calling_and_properties(tmp_path: Path) -> None:
    """Verify Gemini function_call parts are extracted and properties accessible."""

    class MockGeminiModel:
        def __init__(self) -> None:
            self.generate_content = MagicMock()

    client = MockGeminiModel()
    mock_raw_response = {
        "text": None,
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "function_call": {
                                "name": "get_current_weather",
                                "args": {"location": "San Francisco, CA"},
                            }
                        }
                    ]
                }
            }
        ],
        "usage_metadata": {
            "prompt_token_count": 15,
            "candidates_token_count": 10,
            "total_token_count": 25,
        },
    }
    client.generate_content.return_value = mock_raw_response
    patch(client, provider="gemini")

    cfg = TraceReplayConfig(fixtures_dir=tmp_path)

    # Record
    with session(name="gemini_fn_call", mode=ReplayMode.RECORD, config=cfg):
        client.generate_content(
            model="gemini-1.5-pro",
            contents="What's the weather in SF?",
            tools=[{"function_declarations": [{"name": "get_current_weather"}]}],
        )

    # Replay
    with session(name="gemini_fn_call", mode=ReplayMode.REPLAY, config=cfg):
        resp_rep = client.generate_content(
            model="gemini-1.5-pro",
            contents="What's the weather in SF?",
            tools=[{"function_declarations": [{"name": "get_current_weather"}]}],
        )
        assert len(resp_rep.function_calls) == 1
        fn_call = resp_rep.function_calls[0]
        assert fn_call.name == "get_current_weather"
        assert fn_call.args == {"location": "San Francisco, CA"}
        assert resp_rep.candidates[0].content.parts[0].function_call.name == "get_current_weather"

    unpatch(client)


def test_patcher_auto_detect_all_providers() -> None:
    """Verify _resolve_adapter resolves all provider types cleanly."""

    class GenericOllamaClient:
        base_url = "http://localhost:11434/v1"
        chat = MagicMock()

    class GenericVLLMClient:
        base_url = "http://localhost:8000/v1"
        chat = MagicMock()

    class MistralAiClient:
        chat = MagicMock()

        def __init__(self) -> None:
            self.chat.complete = MagicMock()

    adapter_mistral = _resolve_adapter(MistralAiClient())
    assert isinstance(adapter_mistral, MistralAdapter)

    adapter_ollama = _resolve_adapter(GenericOllamaClient())
    assert adapter_ollama.provider_name == "ollama"

    adapter_vllm = _resolve_adapter(GenericVLLMClient())
    assert isinstance(adapter_vllm, GenericOpenAIAdapter)

    # Explicit provider hints
    dummy = MagicMock()
    dummy.chat.completions.create = MagicMock()
    assert _resolve_adapter(dummy, provider="generic").provider_name == "generic"
    assert _resolve_adapter(dummy, provider="deepseek").provider_name == "deepseek"
    assert _resolve_adapter(dummy, provider="groq").provider_name == "groq"
