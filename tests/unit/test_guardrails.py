"""Comprehensive unit tests for Token, Cost & Latency Guardrails (Feature 3).

Verifies:
1. Standard model pricing resolution, fuzzy matching, and cost calculation.
2. Token budget caps (total tokens, prompt tokens, completion tokens, per-request tokens).
3. Cost budget caps (cumulative USD cost and per-request USD cost).
4. Custom model pricing overrides.
5. Latency budget caps (per-request latency and cumulative session duration).
6. Enforcement actions: RAISE, WARN, and RECORD_ONLY.
7. Replay mode offline guardrail enforcement catching regressions with zero live API calls.
8. Async execution guardrail enforcement.
9. Local tool execution latency tracking with @record_tool.
10. Pytest marker integration (@pytest.mark.trace_replay(max_cost_usd=..., max_tokens=...)).
11. Guardrail diagnostic reports and serialization.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from tracereplay.agent import record_tool
from tracereplay.config import TraceReplayConfig
from tracereplay.core.session import session
from tracereplay.exceptions import (
    CostBudgetExceededError,
    LatencyBudgetExceededError,
    TokenBudgetExceededError,
)
from tracereplay.guardrails import (
    GuardrailAction,
    GuardrailConfig,
    calculate_token_cost,
    cost_budget,
    latency_budget,
    normalize_model_identifier,
    token_budget,
)
from tracereplay.models import ReplayMode
from tracereplay.providers.patcher import patch, unpatch
from tracereplay.pytest_plugin import create_tracereplay_session

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
    """Mock client returning controlled prompt and completion token counts."""

    def __init__(
        self,
        prompt_tokens: int = 50,
        completion_tokens: int = 25,
        model: str = "gpt-4o",
        delay_seconds: float = 0.0,
    ) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.model_name = model
        self.delay_seconds = delay_seconds

        def default_create(*args: Any, **kwargs: Any) -> Any:
            if self.delay_seconds > 0:
                time.sleep(self.delay_seconds)
            used_model = kwargs.get("model", self.model_name)
            p_tok = kwargs.get("prompt_tokens", self.prompt_tokens)
            c_tok = kwargs.get("completion_tokens", self.completion_tokens)
            return {
                "id": "chatcmpl_mock_gr",
                "model": used_model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Mock Answer"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": p_tok,
                    "completion_tokens": c_tok,
                    "total_tokens": p_tok + c_tok,
                },
            }

        self.chat = MockChat(default_create)


class MockAsyncCompletions:
    def __init__(self, handler: Callable[..., Any]) -> None:
        self.create = handler


class MockAsyncChat:
    def __init__(self, handler: Callable[..., Any]) -> None:
        self.completions = MockAsyncCompletions(handler)


class MockAsyncOpenAIClient:
    def __init__(
        self,
        prompt_tokens: int = 60,
        completion_tokens: int = 40,
        model: str = "gpt-4o",
    ) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.model_name = model

        async def default_create(*args: Any, **kwargs: Any) -> Any:
            used_model = kwargs.get("model", self.model_name)
            return {
                "id": "chatcmpl_async_mock_gr",
                "model": used_model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Async Mock Answer"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": self.prompt_tokens,
                    "completion_tokens": self.completion_tokens,
                    "total_tokens": self.prompt_tokens + self.completion_tokens,
                },
            }

        self.chat = MockAsyncChat(default_create)


# ============================================================================
# Pricing & Normalization Unit Tests
# ============================================================================


def test_pricing_catalog_rates_and_normalization() -> None:
    """Verify model string normalization and accurate standard pricing lookup."""
    assert normalize_model_identifier("gpt-4o-2024-08-06") == "gpt-4o"
    assert normalize_model_identifier("claude-3-5-sonnet-20241022") == "claude-3-5-sonnet"
    assert normalize_model_identifier("models/gemini-1.5-flash-latest") == "gemini-1.5-flash"

    # GPT-4o standard: $2.50 / 1M prompt, $10.00 / 1M completion
    # 10,000 prompt tokens = $0.025, 5,000 completion tokens = $0.050 -> Total = $0.075
    cost = calculate_token_cost(
        model="gpt-4o",
        prompt_tokens=10_000,
        completion_tokens=5_000,
    )
    assert abs(cost - 0.075) < 1e-5

    # Claude 3.5 Sonnet: $3.00 / 1M prompt, $15.00 / 1M completion
    cost_claude = calculate_token_cost(
        model="claude-3-5-sonnet-20241022",
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
    )
    assert abs(cost_claude - 18.00) < 1e-4

    # Gemini 1.5 Flash: $0.075 / 1M prompt, $0.30 / 1M completion
    cost_gemini = calculate_token_cost(
        model="gemini-1.5-flash",
        prompt_tokens=100_000,
        completion_tokens=100_000,
    )
    assert abs(cost_gemini - 0.0375) < 1e-5


def test_custom_pricing_overrides() -> None:
    """Verify custom pricing dictionary takes precedence over standard catalog."""
    custom_map = {"my-custom-finetune": (5.0, 20.0)}

    cost = calculate_token_cost(
        model="my-custom-finetune",
        prompt_tokens=1_000_000,
        completion_tokens=500_000,
        custom_pricing=custom_map,
    )
    # $5.00 + $10.00 = $15.00
    assert abs(cost - 15.0) < 1e-4


# ============================================================================
# Token Budget Guardrail Tests
# ============================================================================


def test_cumulative_total_token_budget_breach(tmp_path: Path) -> None:
    """Verify TokenBudgetExceededError is raised when total tokens exceed limit."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient(prompt_tokens=60, completion_tokens=40)  # 100 per call
    client = patch(raw_client, provider="openai")

    # Set cumulative limit of 150 tokens
    guard = token_budget(max_tokens=150)

    with (
        session("token_cap_test", mode=ReplayMode.RECORD, guardrails=guard, config=cfg) as sess,
        pytest.raises(TokenBudgetExceededError) as exc_info,
    ):
        # 1st call: consumes 100 tokens (Cumulative: 100 <= 150 -> OK)
        client.chat.completions.create(messages=[{"role": "user", "content": "Call 1"}])
        assert sess.guardrail_report is not None
        assert sess.guardrail_report.total_tokens == 100

        # 2nd call: consumes 100 tokens (Cumulative: 200 > 150 -> BREACH)
        client.chat.completions.create(messages=[{"role": "user", "content": "Call 2"}])

    unpatch(raw_client)

    err = exc_info.value
    assert err.threshold == 150.0
    assert err.actual == 200.0
    assert err.metric == "total_tokens"


def test_prompt_and_completion_token_caps(tmp_path: Path) -> None:
    """Verify granular prompt and completion token constraints."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient(prompt_tokens=120, completion_tokens=30)
    client = patch(raw_client, provider="openai")

    guard = GuardrailConfig(max_prompt_tokens=100)

    with (
        session("prompt_cap_test", mode=ReplayMode.RECORD, guardrails=guard, config=cfg),
        pytest.raises(TokenBudgetExceededError) as exc_info,
    ):
        client.chat.completions.create(messages=[{"role": "user", "content": "Prompt Test"}])

    unpatch(raw_client)
    assert exc_info.value.metric == "prompt_tokens"
    assert exc_info.value.actual == 120.0
    assert exc_info.value.threshold == 100.0


def test_per_request_token_cap(tmp_path: Path) -> None:
    """Verify max_request_tokens stops an oversized prompt immediately."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient(prompt_tokens=300, completion_tokens=50)  # 350 tokens
    client = patch(raw_client, provider="openai")

    guard = GuardrailConfig(max_request_tokens=200)

    with (
        session("req_tok_test", mode=ReplayMode.RECORD, guardrails=guard, config=cfg),
        pytest.raises(TokenBudgetExceededError) as exc_info,
    ):
        client.chat.completions.create(messages=[{"role": "user", "content": "Huge payload"}])

    unpatch(raw_client)
    assert exc_info.value.metric == "request_tokens"
    assert exc_info.value.actual == 350.0


# ============================================================================
# Cost Budget Guardrail Tests
# ============================================================================


def test_cumulative_cost_budget_breach(tmp_path: Path) -> None:
    """Verify CostBudgetExceededError is raised when financial cost exceeds budget in USD."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    # gpt-4o: $2.50 / 1M prompt, $10.00 / 1M completion
    # 10,000 prompt = $0.025, 2,000 completion = $0.020 -> Total = $0.045 per call
    raw_client = MockOpenAIClient(
        prompt_tokens=10_000,
        completion_tokens=2_000,
        model="gpt-4o",
    )
    client = patch(raw_client, provider="openai")

    # Set hard financial stop at $0.060 USD
    guard = cost_budget(max_cost_usd=0.060)

    with (
        session("cost_budget_test", mode=ReplayMode.RECORD, guardrails=guard, config=cfg) as sess,
        pytest.raises(CostBudgetExceededError) as exc_info,
    ):
        # 1st call: $0.045 <= $0.060 -> OK
        client.chat.completions.create(messages=[{"role": "user", "content": "Task 1"}])
        assert sess.guardrail_report is not None
        assert abs(sess.guardrail_report.total_cost_usd - 0.045) < 1e-4

        # 2nd call: Cumulative $0.090 > $0.060 -> BREACH
        client.chat.completions.create(messages=[{"role": "user", "content": "Task 2"}])

    unpatch(raw_client)

    err = exc_info.value
    assert err.threshold == 0.060
    assert abs(err.actual - 0.090) < 1e-4
    assert err.metric == "total_cost"


def test_per_request_cost_budget_breach(tmp_path: Path) -> None:
    """Verify max_request_cost_usd catches single expensive model calls."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    # claude-3-opus: $15.00 / 1M prompt, $75.00 / 1M completion
    # 5,000 prompt ($0.075) + 1,000 completion ($0.075) = $0.150 per call
    raw_client = MockOpenAIClient(
        prompt_tokens=5_000,
        completion_tokens=1_000,
        model="claude-3-opus",
    )
    client = patch(raw_client, provider="openai")

    guard = GuardrailConfig(max_request_cost_usd=0.100)

    with (
        session("per_req_cost", mode=ReplayMode.RECORD, guardrails=guard, config=cfg),
        pytest.raises(CostBudgetExceededError) as exc_info,
    ):
        client.chat.completions.create(
            model="claude-3-opus",
            messages=[{"role": "user", "content": "Opus Query"}],
        )

    unpatch(raw_client)
    assert exc_info.value.metric == "request_cost"
    assert exc_info.value.threshold == 0.100
    assert abs(exc_info.value.actual - 0.150) < 1e-4


# ============================================================================
# Latency Guardrail Tests
# ============================================================================


def test_latency_budget_per_request_breach(tmp_path: Path) -> None:
    """Verify LatencyBudgetExceededError is raised when an LLM call exceeds duration limit."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    # Inject 0.06s (60ms) artificial delay
    raw_client = MockOpenAIClient(delay_seconds=0.06)
    client = patch(raw_client, provider="openai")

    # Set per-request max latency to 40ms
    guard = latency_budget(max_request_latency_ms=40.0)

    with (
        session("latency_test", mode=ReplayMode.RECORD, guardrails=guard, config=cfg),
        pytest.raises(LatencyBudgetExceededError) as exc_info,
    ):
        client.chat.completions.create(messages=[{"role": "user", "content": "Slow Call"}])

    unpatch(raw_client)
    assert exc_info.value.metric == "request_latency"
    assert exc_info.value.threshold == 40.0
    assert exc_info.value.actual >= 50.0


# ============================================================================
# Action Modes: WARN and RECORD_ONLY Tests
# ============================================================================


def test_guardrail_action_warn_emits_warning_without_halting(tmp_path: Path) -> None:
    """Verify GuardrailAction.WARN emits a UserWarning and allows test execution to continue."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient(prompt_tokens=200, completion_tokens=100)  # 300 tokens
    client = patch(raw_client, provider="openai")

    # Cap at 150 tokens, but configured with WARN action
    guard = GuardrailConfig(max_tokens=150, action=GuardrailAction.WARN)

    with (
        session("warn_test", mode=ReplayMode.RECORD, guardrails=guard, config=cfg) as sess,
        pytest.warns(UserWarning, match="Cumulative total tokens") as record,
    ):
        resp = client.chat.completions.create(messages=[{"role": "user", "content": "Warn"}])
        assert resp["choices"][0]["message"]["content"] == "Mock Answer"

    unpatch(raw_client)
    assert len(record) == 1
    assert sess.guardrail_report is not None
    assert len(sess.guardrail_report.violations) == 1
    assert sess.guardrail_report.passed is True  # In WARN mode, report passes


def test_guardrail_action_record_only(tmp_path: Path) -> None:
    """Verify GuardrailAction.RECORD_ONLY logs violations silently in report."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient(prompt_tokens=500, completion_tokens=500)
    client = patch(raw_client, provider="openai")

    guard = GuardrailConfig(max_tokens=200, action=GuardrailAction.RECORD_ONLY)

    with session("record_only_test", mode=ReplayMode.RECORD, guardrails=guard, config=cfg) as sess:
        resp = client.chat.completions.create(messages=[{"role": "user", "content": "Silent"}])
        assert resp["choices"][0]["message"]["content"] == "Mock Answer"

    unpatch(raw_client)
    assert sess.guardrail_report is not None
    assert len(sess.guardrail_report.violations) == 1
    assert sess.guardrail_report.violations[0].actual == 1000.0


# ============================================================================
# Replay Mode Offline Guardrail Enforcement
# ============================================================================


def test_replay_mode_offline_regression_guardrail(tmp_path: Path) -> None:
    """Verify Guardrails catch prompt and cost regressions during REPLAY with 0 live API calls."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient(prompt_tokens=800, completion_tokens=200, model="gpt-4o")
    client = patch(raw_client, provider="openai")

    # 1. Record baseline interaction
    with session("baseline_audit", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Analyze code"}])

    # 2. Replay with strict regression budget: max_tokens=500 (Baseline used 1000)
    regression_guard = GuardrailConfig(max_tokens=500)

    with (
        session(
            "baseline_audit",
            mode=ReplayMode.REPLAY,
            guardrails=regression_guard,
            config=cfg,
        ),
        pytest.raises(TokenBudgetExceededError) as exc_info,
    ):
        client.chat.completions.create(messages=[{"role": "user", "content": "Analyze code"}])

    unpatch(raw_client)
    assert exc_info.value.threshold == 500.0
    assert exc_info.value.actual == 1000.0


# ============================================================================
# Tool Execution Duration Guardrail Tests
# ============================================================================


def test_tool_execution_latency_guardrail(tmp_path: Path) -> None:
    """Verify local tool functions decorated with @record_tool trigger latency guardrails."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)

    @record_tool(name="slow_database_lookup")
    def slow_database_lookup(user_id: str) -> dict[str, str]:
        time.sleep(0.05)  # 50ms simulated DB latency
        return {"user_id": user_id, "status": "active"}

    guard = latency_budget(max_request_latency_ms=30.0)

    with (
        session("tool_latency_test", mode=ReplayMode.RECORD, guardrails=guard, config=cfg),
        pytest.raises(LatencyBudgetExceededError) as exc_info,
    ):
        slow_database_lookup(user_id="user_123")

    assert exc_info.value.metric == "request_latency"
    assert exc_info.value.threshold == 30.0
    assert exc_info.value.actual >= 40.0


# ============================================================================
# Async Guardrail Tests
# ============================================================================


@pytest.mark.asyncio
async def test_async_guardrail_enforcement(tmp_path: Path) -> None:
    """Verify asynchronous client interactions enforce token and cost guardrails."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockAsyncOpenAIClient(prompt_tokens=300, completion_tokens=100)
    client = patch(raw_client, provider="openai")

    guard = token_budget(max_tokens=250)

    with (
        session("async_guard_test", mode=ReplayMode.RECORD, guardrails=guard, config=cfg),
        pytest.raises(TokenBudgetExceededError) as exc_info,
    ):
        await client.chat.completions.create(messages=[{"role": "user", "content": "Async Hello"}])

    unpatch(raw_client)
    assert exc_info.value.actual == 400.0
    assert exc_info.value.threshold == 250.0


# ============================================================================
# Pytest Marker Integration Tests
# ============================================================================


def test_pytest_marker_guardrail_kwargs_integration(tmp_path: Path) -> None:
    """Verify @pytest.mark.trace_replay(max_cost_usd=..., max_tokens=...) initializes Guardrails."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)

    mock_marker = MagicMock()
    mock_marker.args = ()
    mock_marker.kwargs = {
        "fixture": "marker_guardrail_fixture",
        "mode": "record",
        "max_cost_usd": 0.05,
        "max_tokens": 1500,
        "max_latency_ms": 2500.0,
    }

    mock_request = MagicMock()
    mock_request.config.getoption.return_value = False
    mock_request.node.get_closest_marker.return_value = mock_marker
    mock_request.node.callspec = None
    mock_request.node.name = "test_marker_guardrail"

    gen = create_tracereplay_session(mock_request, cfg)
    sess = next(gen)
    try:
        assert sess.guardrail_engine is not None
        assert sess.guardrail_engine.config.max_cost_usd == 0.05
        assert sess.guardrail_engine.config.max_tokens == 1500
        assert sess.guardrail_engine.config.max_latency_ms == 2500.0
    finally:
        with contextlib.suppress(StopIteration):
            next(gen)


# ============================================================================
# Guardrail Report & Diagnostic Summary Tests
# ============================================================================


def test_guardrail_report_breakdown_and_summary_text(tmp_path: Path) -> None:
    """Verify GuardrailReport compiles exact model cost breakdowns and formatted text."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    raw_client = MockOpenAIClient(prompt_tokens=1000, completion_tokens=500, model="gpt-4o")
    client = patch(raw_client, provider="openai")

    with session("report_test", mode=ReplayMode.RECORD, max_tokens=5000, config=cfg) as sess:
        client.chat.completions.create(messages=[{"role": "user", "content": "Query 1"}])
        client.chat.completions.create(messages=[{"role": "user", "content": "Query 2"}])

        rep = sess.guardrail_report
        assert rep is not None
        assert rep.passed is True
        assert rep.interaction_count == 2
        assert rep.total_tokens == 3000
        assert rep.total_prompt_tokens == 2000
        assert rep.total_completion_tokens == 1000
        assert "gpt-4o" in rep.cost_breakdown_by_model

        summary = rep.summary_text()
        assert "Guardrail Report: PASSED" in summary
        assert "Total Tokens: 3,000" in summary
        assert "gpt-4o" in summary

        data = sess.budget_summary
        assert data is not None
        assert data["total_tokens"] == 3000
        assert data["passed"] is True

    unpatch(raw_client)
