"""Unit tests for Phase 8: Multi-turn agent execution tracking and tool-call recording."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tracereplay import (
    AgentStepType,
    AgentTracker,
    ReplayMode,
    RequestPayload,
    ResponsePayload,
    ToolExecutionError,
    record_tool,
    session,
)
from tracereplay.config import TraceReplayConfig

# ============================================================================
# 1. AgentTracker Tests
# ============================================================================


def test_agent_tracker_steps_and_visualization() -> None:
    tracker = AgentTracker(agent_name="support_bot")

    # Step 0: User input
    s0 = tracker.add_user_input(
        "What is my current subscription plan?",
        metadata={"user_id": "u42"},
    )
    assert s0.step_index == 0
    assert s0.step_type == AgentStepType.USER_INPUT
    assert s0.data["prompt"] == "What is my current subscription plan?"
    assert s0.data["user_id"] == "u42"

    # Step 1: LLM decision to call a tool
    s1 = tracker.add_llm_decision(
        decision="Call get_subscription tool",
        tool_calls=[{"name": "get_subscription", "arguments": {"user_id": "u42"}}],
    )
    assert s1.step_index == 1
    assert s1.step_type == AgentStepType.LLM_DECISION

    # Step 2: Tool execution
    s2 = tracker.add_tool_execution(
        tool_name="get_subscription",
        arguments={"user_id": "u42"},
    )
    assert s2.step_index == 2
    assert s2.step_type == AgentStepType.TOOL_EXECUTION

    # Step 3: Tool result
    s3 = tracker.add_tool_result(
        tool_name="get_subscription",
        result={"plan": "Enterprise Pro", "active": True},
        duration_ms=12.5,
    )
    assert s3.step_index == 3
    assert s3.step_type == AgentStepType.TOOL_RESULT
    assert s3.duration_ms == 12.5

    # Step 4: Final answer
    s4 = tracker.add_final_answer("You are currently on the Enterprise Pro plan.")
    assert s4.step_index == 4
    assert s4.step_type == AgentStepType.FINAL_ANSWER
    assert tracker.total_steps == 5

    # Visualization
    flow = tracker.visualize_flow()
    assert "Agent Flow [support_bot]:" in flow
    assert "USER_INPUT" in flow
    assert "LLM_DECISION" in flow
    assert "TOOL_EXECUTION" in flow
    assert "TOOL_RESULT" in flow
    assert "FINAL_ANSWER" in flow

    # Serialization fidelity
    serialized = tracker.to_dict()
    assert serialized["agent_name"] == "support_bot"
    assert len(serialized["steps"]) == 5

    restored = AgentTracker.from_dict(serialized)
    assert restored.agent_name == "support_bot"
    assert restored.total_steps == 5
    assert restored.steps[0].data["prompt"] == "What is my current subscription plan?"
    assert restored.steps[4].data["answer"] == "You are currently on the Enterprise Pro plan."


def test_agent_tracker_empty_flow() -> None:
    tracker = AgentTracker(agent_name="empty_agent")
    assert tracker.total_steps == 0
    assert tracker.visualize_flow() == "Agent Flow [empty_agent]: (empty)"


# ============================================================================
# 2. @record_tool Decorator Tests (Sync & Async)
# ============================================================================


def test_record_tool_passthrough_when_no_active_session() -> None:
    @record_tool
    def add(a: int, b: int) -> int:
        return a + b

    assert add(3, 4) == 7


@pytest.mark.asyncio
async def test_record_tool_async_passthrough_when_no_active_session() -> None:
    @record_tool
    async def async_multiply(a: int, b: int) -> int:
        return a * b

    res = await async_multiply(3, 4)
    assert res == 12


def test_record_tool_sync_record_and_replay(tmp_path: Path) -> None:
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    real_invocations = 0

    @record_tool
    def compute_metric(value: float, factor: float = 2.0) -> float:
        nonlocal real_invocations
        real_invocations += 1
        return value * factor

    # Phase A: RECORD
    with session("metric_session", mode=ReplayMode.RECORD, config=cfg) as sess:
        assert sess.recorder is not None
        res1 = compute_metric(10.0, factor=3.0)
        assert res1 == 30.0
        assert real_invocations == 1

        res2 = compute_metric(5.0)
        assert res2 == 10.0
        assert real_invocations == 2

    # Verify fixture file was persisted
    fixture_file = tmp_path / "metric_session.json"
    assert fixture_file.exists()

    # Phase B: REPLAY (real function must NOT be executed again)
    with session("metric_session", mode=ReplayMode.REPLAY, config=cfg) as sess:
        assert sess.replayer is not None
        rep1 = compute_metric(10.0, factor=3.0)
        assert rep1 == 30.0
        assert real_invocations == 2  # Has not incremented!

        rep2 = compute_metric(5.0)
        assert rep2 == 10.0
        assert real_invocations == 2  # Has not incremented!


@pytest.mark.asyncio
async def test_record_tool_async_record_and_replay(tmp_path: Path) -> None:
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    real_calls = 0

    @record_tool(name="fetch_remote_data")
    async def fetch_remote_data(endpoint: str) -> dict[str, str]:
        nonlocal real_calls
        real_calls += 1
        return {"endpoint": endpoint, "status": "ok"}

    # RECORD
    async with session("async_tool_session", mode=ReplayMode.RECORD, config=cfg):
        out1 = await fetch_remote_data("https://api.example.com/v1")
        assert out1 == {"endpoint": "https://api.example.com/v1", "status": "ok"}
        assert real_calls == 1

    # REPLAY
    async with session("async_tool_session", mode=ReplayMode.REPLAY, config=cfg):
        out2 = await fetch_remote_data("https://api.example.com/v1")
        assert out2 == {"endpoint": "https://api.example.com/v1", "status": "ok"}
        assert real_calls == 1  # Unchanged!


def test_record_tool_ignore_args(tmp_path: Path) -> None:
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)

    @record_tool(ignore_args=["client_context"])
    def query_service(item_id: str, client_context: Any = None) -> str:
        return f"result_for_{item_id}"

    # In RECORD mode: client_context should not be in recorded arguments
    with session("ignore_args_session", mode=ReplayMode.RECORD, config=cfg) as sess:
        res = query_service("item_999", client_context={"sensitive": "token_123"})
        assert res == "result_for_item_999"
        assert sess.recorder is not None
        assert len(sess.recorder.tool_executions) == 1
        assert "client_context" not in sess.recorder.tool_executions[0].arguments
        assert sess.recorder.tool_executions[0].arguments == {"item_id": "item_999"}

    # In REPLAY mode: different client_context passes because it is ignored
    with session("ignore_args_session", mode=ReplayMode.REPLAY, config=cfg):
        rep = query_service("item_999", client_context={"sensitive": "different_token"})
        assert rep == "result_for_item_999"


# ============================================================================
# 3. Mismatch and Exhaustion Failure Modes
# ============================================================================


def test_tool_execution_name_mismatch(tmp_path: Path) -> None:
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)

    @record_tool(name="tool_first")
    def tool_first(val: int) -> int:
        return val * 2

    @record_tool(name="tool_second")
    def tool_second(val: int) -> int:
        return val * 3

    with session("order_session", mode=ReplayMode.RECORD, config=cfg):
        tool_first(5)

    with session("order_session", mode=ReplayMode.REPLAY, config=cfg):
        with pytest.raises(ToolExecutionError) as exc_info:
            tool_second(5)
        assert "Tool name mismatch at index 0" in str(exc_info.value)
        assert exc_info.value.details["expected_function"] == "tool_first"
        assert exc_info.value.details["actual_function"] == "tool_second"


def test_tool_execution_argument_mismatch(tmp_path: Path) -> None:
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)

    @record_tool
    def search_records(query: str, limit: int = 5) -> list[str]:
        return [f"match_{query}"]

    with session("arg_session", mode=ReplayMode.RECORD, config=cfg):
        search_records("quantum physics", limit=5)

    with session("arg_session", mode=ReplayMode.REPLAY, config=cfg):
        with pytest.raises(ToolExecutionError) as exc_info:
            search_records("general relativity", limit=5)
        assert "Tool argument mismatch for 'search_records'" in str(exc_info.value)
        assert exc_info.value.details["expected_arguments"] == {
            "query": "quantum physics",
            "limit": 5,
        }
        assert exc_info.value.details["actual_arguments"] == {
            "query": "general relativity",
            "limit": 5,
        }


def test_tool_execution_exhaustion(tmp_path: Path) -> None:
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)

    @record_tool
    def ping() -> str:
        return "pong"

    with session("ping_session", mode=ReplayMode.RECORD, config=cfg):
        ping()

    with session("ping_session", mode=ReplayMode.REPLAY, config=cfg):
        assert ping() == "pong"
        with pytest.raises(ToolExecutionError) as exc_info:
            ping()
        assert "No more recorded tool executions in session" in str(exc_info.value)


# ============================================================================
# 4. Multi-Turn Autonomous Agent Workflow Integration Test
# ============================================================================


def test_multi_turn_autonomous_agent_workflow(tmp_path: Path) -> None:
    """Full multi-turn autonomous agent test:

    User Prompt -> LLM Decision 1 -> Tool Call (weather) -> Tool Result
               -> LLM Decision 2 -> Final Answer
    """
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    tracker = AgentTracker(agent_name="travel_agent")

    tool_call_count = 0

    @record_tool(name="lookup_weather")
    def lookup_weather(city: str) -> dict[str, str]:
        nonlocal tool_call_count
        tool_call_count += 1
        return {"city": city, "condition": "Sunny", "temperature": "24C"}

    class MockLLMClient:
        def __init__(self, mode: str) -> None:
            self.mode = mode
            self.turns = 0

        def ask(self, prompt: str, sess: Any) -> str:
            self.turns += 1
            if self.mode == "RECORD":
                if self.turns == 1:
                    decision_json = (
                        '{"action": "call_tool", "tool": "lookup_weather", '
                        '"arguments": {"city": "Paris"}}'
                    )
                    resp = ResponsePayload(content=decision_json)
                else:
                    resp = ResponsePayload(
                        content="The weather in Paris is Sunny with a temperature of 24C."
                    )
                req = RequestPayload(provider="mock_llm", model="mock-model", prompt=prompt)
                sess.recorder.record_interaction(req, resp)
                return resp.content or ""
            else:
                # In REPLAY mode, fetch from replayer
                req = RequestPayload(provider="mock_llm", model="mock-model", prompt=prompt)
                resp = sess.replayer.replay_interaction(req)
                return resp.content or ""

    def run_agent_loop(
        client: MockLLMClient,
        user_query: str,
        sess: Any,
        agent_tracker: AgentTracker,
    ) -> str:
        agent_tracker.add_user_input(user_query)

        # Turn 1: LLM decides to call a tool
        prompt_1 = f"User asks: {user_query}. Decide next step."
        raw_decision = client.ask(prompt_1, sess)
        agent_tracker.add_llm_decision(raw_decision)

        # Agent parses decision and invokes tool
        tool_out = lookup_weather(city="Paris")
        agent_tracker.add_tool_result("lookup_weather", tool_out)

        # Turn 2: LLM processes tool output and produces final answer
        prompt_2 = f"Tool output: {tool_out}. Formulate final response."
        final_answer = client.ask(prompt_2, sess)
        agent_tracker.add_final_answer(final_answer)

        return final_answer

    # --- Phase A: RECORD ---
    client_rec = MockLLMClient(mode="RECORD")
    with session("travel_session", mode=ReplayMode.RECORD, config=cfg) as sess_rec:
        ans_rec = run_agent_loop(client_rec, "What is the weather in Paris?", sess_rec, tracker)
        assert ans_rec == "The weather in Paris is Sunny with a temperature of 24C."
        assert tool_call_count == 1
        assert tracker.total_steps == 4

    # --- Phase B: REPLAY ---
    tracker_rep = AgentTracker(agent_name="travel_agent_replay")
    client_rep = MockLLMClient(mode="REPLAY")
    with session("travel_session", mode=ReplayMode.REPLAY, config=cfg) as sess_rep:
        ans_rep = run_agent_loop(client_rep, "What is the weather in Paris?", sess_rep, tracker_rep)
        assert ans_rep == "The weather in Paris is Sunny with a temperature of 24C."
        # Tool call count remains exactly 1 (real tool was NEVER executed in replay mode)
        assert tool_call_count == 1
        assert tracker_rep.total_steps == 4
