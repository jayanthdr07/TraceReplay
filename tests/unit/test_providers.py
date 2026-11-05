"""Unit tests for the provider abstraction layer and OpenAI client adapter."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tracereplay.config import TraceReplayConfig
from tracereplay.core import session
from tracereplay.models import ReplayMode
from tracereplay.providers import patch, unpatch


class MockCompletions:
    def __init__(self, handler: Callable[..., Any]) -> None:
        self.create = handler


class MockChat:
    def __init__(self, handler: Callable[..., Any]) -> None:
        self.completions = MockCompletions(handler)


class MockOpenAIClient:
    def __init__(self, response_fn: Callable[..., Any] | None = None) -> None:
        def default_create(*args: Any, **kwargs: Any) -> Any:
            return {
                "id": "chatcmpl_live_123",
                "model": kwargs.get("model", "gpt-4o"),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Live answer from OpenAI",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 6,
                    "total_tokens": 18,
                },
            }

        self.chat = MockChat(response_fn or default_create)


class MockAsyncOpenAIClient:
    def __init__(self, response_fn: Callable[..., Any] | None = None) -> None:
        async def default_create(*args: Any, **kwargs: Any) -> Any:
            return {
                "id": "chatcmpl_async_123",
                "model": kwargs.get("model", "gpt-4o"),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Live async answer",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 15,
                    "completion_tokens": 5,
                    "total_tokens": 20,
                },
            }

        self.chat = MockChat(response_fn or default_create)


def test_sync_record_and_replay_openai_client(tmp_path: Path) -> None:
    """Verify synchronous recording and offline replay with native attribute access."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    session_name = "test_openai_sync"

    live_client = MockOpenAIClient()
    client = patch(live_client)

    # 1. Record Mode
    with session(session_name, mode=ReplayMode.RECORD, config=cfg):
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello world"}],
            temperature=0.7,
        )
        assert resp["choices"][0]["message"]["content"] == "Live answer from OpenAI"

    # 2. Replay Mode (Network must NOT be called)
    def blocked_live_call(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("Network should NOT be accessed during Replay mode!")

    offline_client = MockOpenAIClient(response_fn=blocked_live_call)
    replay_client = patch(offline_client)

    with session(session_name, mode=ReplayMode.REPLAY, config=cfg):
        replayed_resp = replay_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello world"}],
            temperature=0.7,
        )
        assert replayed_resp.choices[0].message.content == "Live answer from OpenAI"
        assert replayed_resp.usage.total_tokens == 18
        assert replayed_resp.model == "gpt-4o"
        assert replayed_resp.choices[0].finish_reason == "stop"


@pytest.mark.asyncio
async def test_async_record_and_replay_openai_client(tmp_path: Path) -> None:
    """Verify asynchronous recording and offline replay."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    session_name = "test_openai_async"

    live_async_client = MockAsyncOpenAIClient()
    client = patch(live_async_client)

    # 1. Record Mode
    async with session(session_name, mode=ReplayMode.RECORD, config=cfg):
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Async prompt"}],
        )
        assert resp["choices"][0]["message"]["content"] == "Live async answer"

    # 2. Replay Mode
    async def blocked_call(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("Network should NOT be accessed during Replay mode!")

    offline_async_client = MockAsyncOpenAIClient(response_fn=blocked_call)
    replay_async_client = patch(offline_async_client)

    async with session(session_name, mode=ReplayMode.REPLAY, config=cfg):
        replayed_resp = await replay_async_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Async prompt"}],
        )
        assert replayed_resp.choices[0].message.content == "Live async answer"
        assert replayed_resp.usage.total_tokens == 20


def test_tool_calls_record_and_replay(tmp_path: Path) -> None:
    """Verify tool call arguments are captured, parsed, and reconstructed."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    session_name = "test_openai_tools"

    def tool_live_create(*args: Any, **kwargs: Any) -> Any:
        return {
            "id": "chatcmpl_tool_1",
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_abc123",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"location": "Tokyo"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {
                "prompt_tokens": 25,
                "completion_tokens": 15,
                "total_tokens": 40,
            },
        }

    client = patch(MockOpenAIClient(response_fn=tool_live_create))

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather in location",
            },
        }
    ]

    with session(session_name, mode=ReplayMode.RECORD, config=cfg):
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "What is the weather in Tokyo?"}],
            tools=tools,
        )
        assert resp["choices"][0]["finish_reason"] == "tool_calls"

    # Replay
    offline_client = patch(MockOpenAIClient(response_fn=None))
    with session(session_name, mode=ReplayMode.REPLAY, config=cfg):
        replayed = offline_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "What is the weather in Tokyo?"}],
            tools=tools,
        )
        assert replayed.choices[0].message.tool_calls is not None
        assert len(replayed.choices[0].message.tool_calls) == 1
        tc = replayed.choices[0].message.tool_calls[0]
        assert tc.id == "call_abc123"
        assert tc.function.name == "get_weather"
        assert tc.function.arguments == '{"location": "Tokyo"}'
        assert replayed.choices[0].finish_reason == "tool_calls"


def test_unpatch_restores_original_method() -> None:
    """Verify unpatching restores original unintercepted method."""
    client = MockOpenAIClient()
    original_func = client.chat.completions.create
    patched = patch(client)
    assert client.chat.completions.create != original_func
    patched.unpatch()
    assert client.chat.completions.create == original_func

    # Test top-level unpatch function
    patched2 = patch(client)
    assert client.chat.completions.create != original_func
    unpatch(patched2)
    assert client.chat.completions.create == original_func
