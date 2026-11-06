"""Comprehensive unit tests for Time-Travel Forking.

Verifies:
1. Replays steps 0..k-1 deterministically at $0 cost and 0ms latency from base fixture.
2. At the fork point, seamlessly switches execution mode to RECORD (or PASSTHROUGH).
3. The newly generated fixture inherits the historical prefix and appends the live branch.
4. Programmatic forking via sess.fork() works mid-trajectory.
5. Forking into PASSTHROUGH mode executes live without persisting to disk.
6. Attempting to fork a non-existent fixture fails fast with FixtureNotFoundError.
7. The resulting branched fixture can subsequently be replayed 100% deterministically.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from tracereplay.agent import record_tool
from tracereplay.config import TraceReplayConfig
from tracereplay.core.session import session
from tracereplay.exceptions import FixtureNotFoundError, TraceReplayError
from tracereplay.models import ReplayMode
from tracereplay.providers.patcher import patch, unpatch
from tracereplay.pytest_plugin import create_tracereplay_session
from tracereplay.storage.json_storage import JsonStorageEngine

# ============================================================================
# Helpers & Client Mocks
# ============================================================================


def get_resp_content(resp: Any) -> str:
    """Helper to extract content from either a live dict or replayed response."""
    if isinstance(resp, dict):
        return str(resp["choices"][0]["message"]["content"])
    return str(resp.choices[0].message.content)


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
                "id": f"chatcmpl_mock_{len(messages)}",
                "model": kwargs.get("model", "gpt-4o"),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": f"Response to: {last_content}",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            }

        self.chat = MockChat(response_fn or default_create)


# ============================================================================
# Test Cases
# ============================================================================


def test_fork_at_step_branches_and_records(tmp_path: Path) -> None:
    """Verify fork_at_step replays prefix from base fixture and records live suffix."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    client_calls: list[str] = []

    def tracking_handler(*args: Any, **kwargs: Any) -> Any:
        messages = kwargs.get("messages", [])
        prompt = messages[-1]["content"]
        client_calls.append(prompt)
        return {
            "id": "chatcmpl_live",
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": f"Live: {prompt}"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    raw_client = MockOpenAIClient(tracking_handler)
    client = patch(raw_client, provider="openai")

    # 1. Record base session with 4 turns: Q0, Q1, Q2, Q3
    with session("base_conversation", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Question 0"}])
        client.chat.completions.create(messages=[{"role": "user", "content": "Question 1"}])
        client.chat.completions.create(messages=[{"role": "user", "content": "Question 2"}])
        client.chat.completions.create(messages=[{"role": "user", "content": "Question 3"}])

    assert len(client_calls) == 4
    client_calls.clear()

    # 2. Fork at step 2 into 'forked_conversation'
    # Steps 0 and 1 should replay (0 live calls).
    # Steps 2 and 3 should execute live and be recorded into 'forked_conversation'.
    with session(
        "base_conversation",
        fork_at_step=2,
        fork_session_name="forked_conversation",
        config=cfg,
    ) as sess:
        assert not sess.is_forked
        assert sess.mode == ReplayMode.REPLAY

        # Step 0: replayed
        r0 = client.chat.completions.create(messages=[{"role": "user", "content": "Question 0"}])
        assert get_resp_content(r0) == "Live: Question 0"
        assert len(client_calls) == 0
        assert not sess.is_forked

        # Step 1: replayed
        r1 = client.chat.completions.create(messages=[{"role": "user", "content": "Question 1"}])
        assert get_resp_content(r1) == "Live: Question 1"
        assert len(client_calls) == 0
        assert not sess.is_forked

        # Step 2: triggers fork! Executes live
        r2 = client.chat.completions.create(
            messages=[{"role": "user", "content": "Diverged Question 2"}]
        )
        assert get_resp_content(r2) == "Live: Diverged Question 2"
        assert len(client_calls) == 1
        assert client_calls[-1] == "Diverged Question 2"
        assert sess.is_forked
        assert sess.mode == ReplayMode.RECORD

        # Step 3: continues in RECORD mode
        r3 = client.chat.completions.create(
            messages=[{"role": "user", "content": "Diverged Question 3"}]
        )
        assert get_resp_content(r3) == "Live: Diverged Question 3"
        assert len(client_calls) == 2
        assert client_calls[-1] == "Diverged Question 3"

    unpatch(raw_client)

    # 3. Verify output files
    base_file = tmp_path / "base_conversation.json"
    forked_file = tmp_path / "forked_conversation.json"

    assert base_file.exists()
    assert forked_file.exists()

    # Verify forked fixture contents
    storage = JsonStorageEngine(config=cfg)
    forked_rec = storage.load("forked_conversation")
    assert len(forked_rec.interactions) == 4

    # Historical steps (0 & 1) inherited from base
    assert forked_rec.interactions[0].request.messages[-1]["content"] == "Question 0"
    assert forked_rec.interactions[1].request.messages[-1]["content"] == "Question 1"
    # Live steps (2 & 3) recorded during fork
    assert forked_rec.interactions[2].request.messages[-1]["content"] == "Diverged Question 2"
    assert forked_rec.interactions[3].request.messages[-1]["content"] == "Diverged Question 3"

    # Base file should still have original Q2 and Q3
    base_rec = storage.load("base_conversation")
    assert len(base_rec.interactions) == 4
    assert base_rec.interactions[2].request.messages[-1]["content"] == "Question 2"
    assert base_rec.interactions[3].request.messages[-1]["content"] == "Question 3"

    # 4. Deterministic playback test: Replay the entire branched fixture with ZERO live calls
    client_calls.clear()
    client_replay = patch(MockOpenAIClient(tracking_handler), provider="openai")

    with session("forked_conversation", mode=ReplayMode.REPLAY, config=cfg):
        c0 = client_replay.chat.completions.create(
            messages=[{"role": "user", "content": "Question 0"}]
        )
        c1 = client_replay.chat.completions.create(
            messages=[{"role": "user", "content": "Question 1"}]
        )
        c2 = client_replay.chat.completions.create(
            messages=[{"role": "user", "content": "Diverged Question 2"}]
        )
        c3 = client_replay.chat.completions.create(
            messages=[{"role": "user", "content": "Diverged Question 3"}]
        )

    assert len(client_calls) == 0  # 100% deterministic replay from branched fixture!
    assert get_resp_content(c0) == "Live: Question 0"
    assert get_resp_content(c1) == "Live: Question 1"
    assert get_resp_content(c2) == "Live: Diverged Question 2"
    assert get_resp_content(c3) == "Live: Diverged Question 3"
    unpatch(client_replay)


def test_fork_at_step_zero(tmp_path: Path) -> None:
    """Verify fork_at_step=0 immediately forks at step 0 without replaying anything."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    calls: list[str] = []

    def handler(*args: Any, **kwargs: Any) -> Any:
        prompt = kwargs["messages"][-1]["content"]
        calls.append(prompt)
        return {
            "id": "chatcmpl_live",
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {"content": f"Ans: {prompt}"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        }

    raw_client = MockOpenAIClient(handler)
    client = patch(raw_client, provider="openai")

    with session("base_single", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Base Prompt"}])

    calls.clear()

    with session(
        "base_single",
        fork_at_step=0,
        fork_session_name="fork_from_start",
        config=cfg,
    ) as sess:
        client.chat.completions.create(messages=[{"role": "user", "content": "New Start"}])
        assert sess.is_forked
        assert sess.mode == ReplayMode.RECORD

    unpatch(raw_client)
    assert len(calls) == 1
    assert calls[0] == "New Start"

    storage = JsonStorageEngine(config=cfg)
    rec = storage.load("fork_from_start")
    assert len(rec.interactions) == 1
    assert rec.interactions[0].request.messages[-1]["content"] == "New Start"


def test_fork_at_tool_by_name(tmp_path: Path) -> None:
    """Verify fork_at_tool switches to RECORD when the designated tool is called."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    tool_invocations: list[str] = []

    @record_tool(name="fetch_balance")
    def fetch_balance(account_id: str) -> dict[str, Any]:
        tool_invocations.append(f"fetch_balance:{account_id}")
        return {"account_id": account_id, "balance": 5000.0}

    @record_tool(name="transfer_funds")
    def transfer_funds(source: str, target: str, amount: float) -> dict[str, Any]:
        tool_invocations.append(f"transfer_funds:{source}->{target}:${amount}")
        return {"status": "transferred", "amount": amount}

    raw_client = MockOpenAIClient()
    client = patch(raw_client, provider="openai")

    # 1. Record original base workflow
    with session("agent_banking", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Check balance"}])
        fetch_balance(account_id="ACC_001")
        client.chat.completions.create(messages=[{"role": "user", "content": "Transfer 100"}])
        transfer_funds(source="ACC_001", target="ACC_002", amount=100.0)

    assert len(tool_invocations) == 2
    tool_invocations.clear()

    # 2. Fork at tool 'transfer_funds':
    # - LLM 0 and fetch_balance should be replayed (tool not executed)
    # - LLM 1 should be replayed
    # - transfer_funds triggers fork! Runs live with different arguments
    # - LLM 2 runs live
    with session(
        "agent_banking",
        fork_at_tool="transfer_funds",
        fork_session_name="agent_banking_diverged",
        config=cfg,
    ) as sess:
        assert not sess.is_forked

        # LLM 0 (replayed)
        client.chat.completions.create(messages=[{"role": "user", "content": "Check balance"}])
        # fetch_balance (replayed, not in tool_invocations)
        bal = fetch_balance(account_id="ACC_001")
        assert bal["balance"] == 5000.0
        assert len(tool_invocations) == 0

        # LLM 1 (replayed)
        client.chat.completions.create(messages=[{"role": "user", "content": "Transfer 100"}])
        assert not sess.is_forked

        # transfer_funds: triggers fork!
        res = transfer_funds(source="ACC_001", target="ACC_999", amount=999.0)
        assert res["status"] == "transferred"
        assert len(tool_invocations) == 1
        assert tool_invocations[0] == "transfer_funds:ACC_001->ACC_999:$999.0"
        assert sess.is_forked
        assert sess.mode == ReplayMode.RECORD

        # LLM 2: recorded live
        client.chat.completions.create(messages=[{"role": "user", "content": "Confirm transfer"}])

    unpatch(raw_client)

    # 3. Verify diverged fixture
    storage = JsonStorageEngine(config=cfg)
    branched_rec = storage.load("agent_banking_diverged")
    assert len(branched_rec.interactions) == 3
    assert len(branched_rec.tool_executions) == 2

    # Tool 0 was replayed from base
    assert branched_rec.tool_executions[0].function_name == "fetch_balance"
    assert branched_rec.tool_executions[0].arguments == {"account_id": "ACC_001"}
    # Tool 1 was live recorded during fork
    assert branched_rec.tool_executions[1].function_name == "transfer_funds"
    assert branched_rec.tool_executions[1].arguments == {
        "source": "ACC_001",
        "target": "ACC_999",
        "amount": 999.0,
    }


def test_fork_at_tool_by_callable(tmp_path: Path) -> None:
    """Verify fork_at_tool accepts function callables in addition to strings."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    call_log: list[str] = []

    @record_tool
    def search_engine(query: str) -> str:
        call_log.append(query)
        return f"Results for {query}"

    with session("tool_callable_base", mode=ReplayMode.RECORD, config=cfg):
        search_engine(query="quantum computing")

    call_log.clear()

    with session(
        "tool_callable_base",
        fork_at_tool=search_engine,  # Passed as callable object
        fork_session_name="tool_callable_fork",
        config=cfg,
    ) as sess:
        search_engine(query="general relativity")
        assert sess.is_forked

    assert len(call_log) == 1
    assert call_log[0] == "general relativity"


def test_fork_at_total_step(tmp_path: Path) -> None:
    """Verify fork_at_total_step counts LLM calls and tool executions combined."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)

    @record_tool(name="calc")
    def calc(x: int) -> int:
        return x * 2

    raw_client = MockOpenAIClient()
    client = patch(raw_client, provider="openai")

    # Record: Step 0 (LLM), Step 1 (Tool), Step 2 (LLM), Step 3 (Tool)
    with session("total_step_base", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Step 0 LLM"}])
        calc(10)
        client.chat.completions.create(messages=[{"role": "user", "content": "Step 2 LLM"}])
        calc(20)

    # Fork at total step 2 (Step 0 LLM and Step 1 Tool replay; Step 2 LLM forks!)
    with session(
        "total_step_base",
        fork_at_total_step=2,
        fork_session_name="total_step_forked",
        config=cfg,
    ) as sess:
        # Step 0: LLM replayed
        client.chat.completions.create(messages=[{"role": "user", "content": "Step 0 LLM"}])
        assert not sess.is_forked

        # Step 1: Tool replayed
        c = calc(10)
        assert c == 20
        assert not sess.is_forked

        # Step 2: total_step reaches 2! Forks before Step 2 LLM call
        client.chat.completions.create(messages=[{"role": "user", "content": "Step 2 Forked"}])
        assert sess.is_forked
        assert sess.mode == ReplayMode.RECORD

    unpatch(raw_client)

    storage = JsonStorageEngine(config=cfg)
    rec = storage.load("total_step_forked")
    assert len(rec.interactions) == 2
    assert rec.interactions[0].request.messages[-1]["content"] == "Step 0 LLM"
    assert rec.interactions[1].request.messages[-1]["content"] == "Step 2 Forked"


def test_fork_to_passthrough_does_not_save_file(tmp_path: Path) -> None:
    """Verify fork_to_mode=PASSTHROUGH switches execution live without writing any new file."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    live_calls: list[str] = []

    def handler(*args: Any, **kwargs: Any) -> Any:
        prompt = kwargs["messages"][-1]["content"]
        live_calls.append(prompt)
        return {
            "id": "chatcmpl_live",
            "model": "gpt-4o",
            "choices": [{"index": 0, "message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    raw_client = MockOpenAIClient(handler)
    client = patch(raw_client, provider="openai")

    with session("base_for_pt", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Base Q"}])

    live_calls.clear()

    target_name = "ephemeral_passthrough_branch"
    with session(
        "base_for_pt",
        fork_at_step=1,
        fork_session_name=target_name,
        fork_to_mode=ReplayMode.PASSTHROUGH,
        config=cfg,
    ) as sess:
        client.chat.completions.create(messages=[{"role": "user", "content": "Base Q"}])
        assert not sess.is_forked

        # Step 1: forks to PASSTHROUGH
        client.chat.completions.create(messages=[{"role": "user", "content": "Live tail"}])
        assert sess.is_forked
        assert sess.mode == ReplayMode.PASSTHROUGH

    unpatch(raw_client)

    assert len(live_calls) == 1
    assert live_calls[0] == "Live tail"

    # Crucial assertion: no new fixture is persisted for PASSTHROUGH
    forked_path = tmp_path / f"{target_name}.json"
    assert not forked_path.exists()


def test_programmatic_fork_during_session(tmp_path: Path) -> None:
    """Verify sess.fork() triggers a programmatic fork at arbitrary points."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    calls: list[str] = []

    def handler(*args: Any, **kwargs: Any) -> Any:
        prompt = kwargs["messages"][-1]["content"]
        calls.append(prompt)
        return {
            "id": "chatcmpl_prog",
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {"content": f"Ans: {prompt}"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        }

    raw_client = MockOpenAIClient(handler)
    client = patch(raw_client, provider="openai")

    with session("prog_base", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Turn 1"}])
        client.chat.completions.create(messages=[{"role": "user", "content": "Turn 2"}])

    calls.clear()

    with session("prog_base", mode=ReplayMode.REPLAY, config=cfg) as sess:
        # Replay turn 1
        client.chat.completions.create(messages=[{"role": "user", "content": "Turn 1"}])
        assert len(calls) == 0

        # Programmatically fork right here
        sess.fork(session_name="prog_forked")
        assert sess.is_forked
        assert sess.mode == ReplayMode.RECORD

        # Calling fork a second time raises an error
        with pytest.raises(TraceReplayError, match="already been forked"):
            sess.fork()

        # Turn 2 is now live
        client.chat.completions.create(messages=[{"role": "user", "content": "Turn 2 Live"}])
        assert len(calls) == 1
        assert calls[0] == "Turn 2 Live"

    unpatch(raw_client)

    storage = JsonStorageEngine(config=cfg)
    rec = storage.load("prog_forked")
    assert len(rec.interactions) == 2
    assert rec.interactions[0].request.messages[-1]["content"] == "Turn 1"
    assert rec.interactions[1].request.messages[-1]["content"] == "Turn 2 Live"


def test_fork_nonexistent_base_fixture_raises_error(tmp_path: Path) -> None:
    """Attempting to fork a non-existent base fixture raises FixtureNotFoundError."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)

    with (
        pytest.raises(FixtureNotFoundError, match="Cannot fork session 'nonexistent_fixture'"),
        session("nonexistent_fixture", fork_at_step=1, config=cfg),
    ):
        pass


def test_pytest_marker_fork_configuration(tmp_path: Path) -> None:
    """Verify pytest trace_replay marker passes forking kwargs to the session."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)

    # Pre-record fixture
    raw_client = MockOpenAIClient()
    client = patch(raw_client, provider="openai")
    with session("marker_fixture", mode=ReplayMode.RECORD, config=cfg):
        client.chat.completions.create(messages=[{"role": "user", "content": "Hello"}])
    unpatch(raw_client)

    # Create mock pytest node and request
    mock_marker = MagicMock()
    mock_marker.args = ()
    mock_marker.kwargs = {
        "fixture": "marker_fixture",
        "fork_at_step": 1,
        "fork_session_name": "marker_forked",
        "fork_to_mode": "record",
    }

    mock_request = MagicMock()
    mock_request.config.getoption.return_value = False
    mock_request.node.get_closest_marker.return_value = mock_marker
    mock_request.node.callspec = None
    mock_request.node.name = "test_marker_fork"

    gen = create_tracereplay_session(mock_request, cfg)
    sess = next(gen)
    try:
        assert sess.fork_at_step == 1
        assert sess.fork_session_name == "marker_forked"
        assert sess.fork_to_mode == ReplayMode.RECORD
        assert sess.is_forking_configured
        assert sess.mode == ReplayMode.REPLAY
    finally:
        with contextlib.suppress(StopIteration):
            next(gen)
