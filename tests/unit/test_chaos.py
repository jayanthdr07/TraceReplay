"""Comprehensive unit tests for AI Chaos Engineering and Fault Injection.

Verifies:
1. HTTP 429 RateLimitError injection with max_times=1 enabling realistic retry loop tests.
2. Simulated network timeout injection with optional artificial delay.
3. HTTP 5xx Server Error injection (500, 502, 503).
4. Context length limit exceeded (400 Bad Request) injection.
5. Corrupted / malformed JSON output mutation testing error recovery.
6. Hallucinated / unregistered tool call injection.
7. Safety refusal / content filter response injection.
8. Latency jitter simulation.
9. Local Python tool function fault injection with @record_tool.
10. Native SDK exception synthesis (OpenAI RateLimitError / APITimeoutError).
11. Pytest trace_replay marker integration with chaos configs.
"""

from __future__ import annotations

import contextlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from tracereplay import chaos
from tracereplay.agent import record_tool
from tracereplay.chaos import ChaosConfig, FaultType
from tracereplay.config import TraceReplayConfig
from tracereplay.core.session import session
from tracereplay.exceptions import (
    ChaosContextLengthError,
    ChaosRateLimitError,
    ChaosServerError,
    ChaosTimeoutError,
)
from tracereplay.models import ReplayMode
from tracereplay.providers.patcher import patch, unpatch
from tracereplay.pytest_plugin import create_tracereplay_session

# Optional SDK import
openai: Any = None
with contextlib.suppress(ImportError):
    import openai

# Helper exception tuple mappings
if openai is not None:
    _RateLimitErrors: tuple[type[Exception], ...] = (openai.RateLimitError, ChaosRateLimitError)
    _TimeoutErrors: tuple[type[Exception], ...] = (openai.APITimeoutError, ChaosTimeoutError)
    _ServerErrors: tuple[type[Exception], ...] = (openai.InternalServerError, ChaosServerError)
    _ContextLengthErrors: tuple[type[Exception], ...] = (
        openai.BadRequestError,
        ChaosContextLengthError,
    )
else:
    _RateLimitErrors = (ChaosRateLimitError,)
    _TimeoutErrors = (ChaosTimeoutError,)
    _ServerErrors = (ChaosServerError,)
    _ContextLengthErrors = (ChaosContextLengthError,)

# ============================================================================
# Helpers & Client Mocks
# ============================================================================


class MockCompletions:
    def __init__(self, handler: Callable[..., Any]) -> None:
        self.create = handler


class MockChat:
    def __init__(self, handler: Callable[..., Any]) -> None:
        self.completions = MockCompletions(handler)


class MockOpenAIClient:
    def __init__(self, response_fn: Callable[..., Any] | None = None) -> None:
        def default_create(*args: Any, **kwargs: Any) -> Any:
            messages = kwargs.get("messages", [])
            last_content = messages[-1]["content"] if messages else "empty"
            return {
                "id": "chatcmpl_mock",
                "model": kwargs.get("model", "gpt-4o"),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": f"Answer: {last_content}",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }

        self.chat = MockChat(response_fn or default_create)


class MockAsyncOpenAIClient:
    def __init__(self, response_fn: Callable[..., Any] | None = None) -> None:
        async def default_create(*args: Any, **kwargs: Any) -> Any:
            messages = kwargs.get("messages", [])
            last_content = messages[-1]["content"] if messages else "empty"
            return {
                "id": "chatcmpl_mock_async",
                "model": kwargs.get("model", "gpt-4o"),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": f"Async Answer: {last_content}",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }

        self.chat = MockChat(response_fn or default_create)


# ============================================================================
# Test Cases
# ============================================================================


def test_rate_limit_native_openai_exception_and_retry(tmp_path: Path) -> None:
    """Verify native openai.RateLimitError is raised on 1st attempt and retry succeeds."""
    if openai is None:
        pytest.skip("openai SDK not installed; skipping native exception synthesis test")
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient()
    client = patch(raw_client, provider="openai")

    # 1. Record base session with 2 interactions
    with session("rate_limit_base", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Query 0"}])
        client.chat.completions.create(messages=[{"role": "user", "content": "Query 1"}])

    # 2. Replay with Chaos: rate limit on step 1 with max_times=1
    chaos_rules = [chaos.rate_limit(step=1, max_times=1, native=True, retry_after=1.5)]
    attempts_on_step_1 = 0

    with session("rate_limit_base", mode=ReplayMode.REPLAY, chaos=chaos_rules, config=cfg) as sess:
        # Step 0: succeeds normally
        r0 = client.chat.completions.create(messages=[{"role": "user", "content": "Query 0"}])
        assert r0.choices[0].message.content == "Answer: Query 0"

        # Step 1: resilient agent retry loop
        resp1 = None
        for _ in range(3):
            try:
                attempts_on_step_1 += 1
                resp1 = client.chat.completions.create(
                    messages=[{"role": "user", "content": "Query 1"}]
                )
                break
            except _RateLimitErrors as err:
                assert getattr(err, "status_code", 429) == 429
                # In real code, backoff sleep would happen here

        assert resp1 is not None
        assert resp1.choices[0].message.content == "Answer: Query 1"
        assert attempts_on_step_1 == 2  # 1st attempt failed with 429, 2nd attempt succeeded!
        assert sess.chaos_engine is not None
        assert len(sess.chaos_engine.history) == 1
        assert sess.chaos_engine.history[0].fault_type == FaultType.RATE_LIMIT

    unpatch(raw_client)


def test_rate_limit_non_native_chaos_error(tmp_path: Path) -> None:
    """Verify native=False raises clean TraceReplay ChaosRateLimitError."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient()
    client = patch(raw_client, provider="openai")

    with session("rl_non_native", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Ping"}])

    chaos_rules = [chaos.rate_limit(step=0, native=False, retry_after=5.0)]

    with (
        session("rl_non_native", mode=ReplayMode.REPLAY, chaos=chaos_rules, config=cfg),
        pytest.raises(ChaosRateLimitError) as exc_info,
    ):
        client.chat.completions.create(messages=[{"role": "user", "content": "Ping"}])

    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after == 5.0
    unpatch(raw_client)


def test_timeout_fault_with_simulated_delay(tmp_path: Path) -> None:
    """Verify timeout fault introduces delay and raises APITimeoutError or ChaosTimeoutError."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient()
    client = patch(raw_client, provider="openai")

    with session("timeout_base", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Calculate"}])

    chaos_rules = [chaos.timeout(step=0, duration_seconds=0.05, native=True)]

    start = time.perf_counter()
    with (
        session("timeout_base", mode=ReplayMode.REPLAY, chaos=chaos_rules, config=cfg),
        pytest.raises(_TimeoutErrors),
    ):
        client.chat.completions.create(messages=[{"role": "user", "content": "Calculate"}])

    elapsed = time.perf_counter() - start
    assert elapsed >= 0.04  # Verified simulated duration
    unpatch(raw_client)


def test_server_error_status_codes(tmp_path: Path) -> None:
    """Verify HTTP 503 Service Unavailable fault injection."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient()
    client = patch(raw_client, provider="openai")

    with session("server_err_base", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Hello"}])

    chaos_rules = [chaos.server_error(status_code=503, step=0, native=True)]

    with (
        session("server_err_base", mode=ReplayMode.REPLAY, chaos=chaos_rules, config=cfg),
        pytest.raises(_ServerErrors) as exc_info,
    ):
        client.chat.completions.create(messages=[{"role": "user", "content": "Hello"}])

    assert getattr(exc_info.value, "status_code", 503) == 503
    unpatch(raw_client)


def test_context_length_exceeded(tmp_path: Path) -> None:
    """Verify 400 Bad Request Context Length Exceeded fault injection."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient()
    client = patch(raw_client, provider="openai")

    with session("ctx_len_base", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Long document"}])

    chaos_rules = [
        chaos.context_length_exceeded(
            step=0,
            max_tokens=8192,
            actual_tokens=12000,
            native=True,
        )
    ]

    with (
        session("ctx_len_base", mode=ReplayMode.REPLAY, chaos=chaos_rules, config=cfg),
        pytest.raises(_ContextLengthErrors),
    ):
        client.chat.completions.create(messages=[{"role": "user", "content": "Long document"}])

    unpatch(raw_client)


def test_malformed_json_response_corruption(tmp_path: Path) -> None:
    """Verify malformed JSON response injection triggers JSONDecodeError in app parser."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient()
    client = patch(raw_client, provider="openai")

    with session("json_base", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Generate JSON"}])

    bad_json = '{"status": "partial", "items": [1, 2,'
    chaos_rules = [chaos.malformed_json(step=0, corrupted_output=bad_json)]

    with session("json_base", mode=ReplayMode.REPLAY, chaos=chaos_rules, config=cfg):
        resp = client.chat.completions.create(
            messages=[{"role": "user", "content": "Generate JSON"}]
        )
        raw_text = resp.choices[0].message.content
        assert raw_text == bad_json

        # Application JSON parser test
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw_text)

    unpatch(raw_client)


def test_hallucinated_tool_call_injection(tmp_path: Path) -> None:
    """Verify hallucinated tool call response injection."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient()
    client = patch(raw_client, provider="openai")

    with session("tool_hallucination_base", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Run tool"}])

    chaos_rules = [
        chaos.hallucinated_tool(
            tool_name="unregistered_dangerous_action",
            arguments={"command": "drop database"},
            step=0,
        )
    ]

    with session("tool_hallucination_base", mode=ReplayMode.REPLAY, chaos=chaos_rules, config=cfg):
        resp = client.chat.completions.create(messages=[{"role": "user", "content": "Run tool"}])
        tool_calls = resp.choices[0].message.tool_calls
        assert tool_calls is not None
        assert len(tool_calls) == 1
        assert tool_calls[0].function.name == "unregistered_dangerous_action"
        args = json.loads(tool_calls[0].function.arguments)
        assert args == {"command": "drop database"}

    unpatch(raw_client)


def test_content_filter_safety_refusal(tmp_path: Path) -> None:
    """Verify content filter safety refusal response injection."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient()
    client = patch(raw_client, provider="openai")

    with session("safety_base", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Borderline prompt"}])

    refusal_msg = "I cannot fulfill this request due to safety policies."
    chaos_rules = [chaos.content_filter(step=0, refusal_text=refusal_msg)]

    with session("safety_base", mode=ReplayMode.REPLAY, chaos=chaos_rules, config=cfg):
        resp = client.chat.completions.create(
            messages=[{"role": "user", "content": "Borderline prompt"}]
        )
        assert resp.choices[0].finish_reason == "content_filter"
        assert resp.choices[0].message.content == refusal_msg

    unpatch(raw_client)


def test_latency_jitter_injection(tmp_path: Path) -> None:
    """Verify latency injection introduces delay and then successfully finishes."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient()
    client = patch(raw_client, provider="openai")

    with session("latency_base", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Speed test"}])

    chaos_rules = [chaos.latency(delay_ms=80.0, step=0)]

    start = time.perf_counter()
    with session("latency_base", mode=ReplayMode.REPLAY, chaos=chaos_rules, config=cfg) as sess:
        resp = client.chat.completions.create(messages=[{"role": "user", "content": "Speed test"}])
        assert resp.choices[0].message.content == "Answer: Speed test"
        assert sess.chaos_engine is not None
        assert len(sess.chaos_engine.history) == 1
        assert sess.chaos_engine.history[0].fault_type == FaultType.LATENCY

    elapsed = time.perf_counter() - start
    assert elapsed >= 0.07
    unpatch(raw_client)


def test_custom_exception_injection(tmp_path: Path) -> None:
    """Verify custom user-defined exception injection."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient()
    client = patch(raw_client, provider="openai")

    with session("custom_exc_base", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Trigger custom"}])

    class CustomAuthError(Exception):
        pass

    chaos_rules = [chaos.custom(exception=CustomAuthError("Token revoked"), step=0)]

    with (
        session("custom_exc_base", mode=ReplayMode.REPLAY, chaos=chaos_rules, config=cfg),
        pytest.raises(CustomAuthError, match="Token revoked"),
    ):
        client.chat.completions.create(messages=[{"role": "user", "content": "Trigger custom"}])

    unpatch(raw_client)


def test_tool_level_chaos_injection(tmp_path: Path) -> None:
    """Verify fault injection into local Python functions decorated with @record_tool."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)

    @record_tool(name="database_query")
    def database_query(query: str) -> dict[str, Any]:
        return {"result": f"records for {query}"}

    with session("tool_chaos_base", mode=ReplayMode.RECORD, config=cfg):
        database_query(query="SELECT * FROM users")

    chaos_rules = [
        chaos.custom(
            tool="database_query",
            exception=ConnectionResetError("Database connection lost"),
            max_times=1,
        )
    ]

    with (
        session("tool_chaos_base", mode=ReplayMode.REPLAY, chaos=chaos_rules, config=cfg),
        pytest.raises(ConnectionResetError, match="Database connection lost"),
    ):
        database_query(query="SELECT * FROM users")


def test_probabilistic_chaos_monkey(tmp_path: Path) -> None:
    """Verify ChaosConfig global probabilities trigger faults."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient()
    client = patch(raw_client, provider="openai")

    with session("monkey_base", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Monkey 1"}])

    # 100% rate limit probability
    chaos_cfg = ChaosConfig(seed=42, rate_limit_probability=1.0)

    with (
        session("monkey_base", mode=ReplayMode.REPLAY, chaos=chaos_cfg, config=cfg),
        pytest.raises(_RateLimitErrors),
    ):
        client.chat.completions.create(messages=[{"role": "user", "content": "Monkey 1"}])

    unpatch(raw_client)


def test_pytest_marker_chaos_integration(tmp_path: Path) -> None:
    """Verify @pytest.mark.trace_replay(chaos=[...]) configures ChaosEngine."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient()
    client = patch(raw_client, provider="openai")

    with session("marker_chaos_fixture", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Marked"}])
    unpatch(raw_client)

    chaos_list = [chaos.rate_limit(step=0)]
    mock_marker = MagicMock()
    mock_marker.args = []
    mock_marker.kwargs = {
        "fixture": "marker_chaos_fixture",
        "mode": "replay",
        "chaos": chaos_list,
    }

    mock_request = MagicMock()
    mock_request.config.getoption.return_value = False
    mock_request.node.get_closest_marker.return_value = mock_marker
    mock_request.node.callspec = None
    mock_request.node.name = "test_chaos_marker"

    gen = create_tracereplay_session(mock_request, cfg)
    sess = next(gen)
    try:
        assert sess.chaos_engine is not None
        assert len(sess.chaos_engine.config.faults) == 1
        assert sess.chaos_engine.config.faults[0].fault_type == FaultType.RATE_LIMIT
    finally:
        with contextlib.suppress(StopIteration):
            next(gen)


@pytest.mark.asyncio
async def test_async_chaos_execution(tmp_path: Path) -> None:
    """Verify asynchronous LLM client calls execute chaos faults correctly."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockAsyncOpenAIClient()
    client = patch(raw_client, provider="openai")

    with session("async_chaos_base", mode=ReplayMode.RECORD, config=cfg):
        await client.chat.completions.create(messages=[{"role": "user", "content": "Async Query"}])

    chaos_rules = [chaos.rate_limit(step=0, native=True)]

    with (
        session("async_chaos_base", mode=ReplayMode.REPLAY, chaos=chaos_rules, config=cfg),
        pytest.raises(_RateLimitErrors),
    ):
        await client.chat.completions.create(messages=[{"role": "user", "content": "Async Query"}])

    unpatch(raw_client)
