"""Example 02: Pytest Plugin Workflow.

Demonstrates how to use the TraceReplay Pytest plugin in test suites:
- Marker: `@pytest.mark.trace_replay(fixture="test_custom_name")`
- Fixture: `tracereplay_session` (automatically injected)
- Automatic mode: Records on first test execution; replays deterministically on subsequent runs.

Run directly with:
    pytest examples/02_pytest_workflow -v
"""

from __future__ import annotations

import pytest

from tracereplay import (
    ReplayMode,
    RequestPayload,
    ResponsePayload,
    TraceReplaySession,
)


def mock_llm_call(prompt: str, session: TraceReplaySession) -> str:
    """Helper representing an application calling an LLM through TraceReplay."""
    req = RequestPayload(provider="openai", model="gpt-4o", prompt=prompt)

    if session.mode == ReplayMode.RECORD:
        resp = ResponsePayload(
            content=f"AI Answer to '{prompt}': The weather in Seattle is 16C with light rain."
        )
        assert session.recorder is not None
        session.recorder.record_interaction(req, resp)
        return resp.content or ""

    elif session.mode == ReplayMode.REPLAY:
        assert session.replayer is not None
        resp = session.replayer.replay_interaction(req)
        return resp.content or ""

    return "Passthrough output"


# ============================================================================
# Pytest Test Cases
# ============================================================================


@pytest.mark.trace_replay(fixture="weather_seattle_query")
def test_weather_bot_response(tracereplay_session: TraceReplaySession) -> None:
    """Verifies that the weather bot provides correct forecast information."""
    assert tracereplay_session.name == "weather_seattle_query"

    answer = mock_llm_call("What is the weather in Seattle?", tracereplay_session)

    assert "Seattle" in answer
    assert "16C" in answer


@pytest.mark.trace_replay
@pytest.mark.parametrize(
    "city,expected_temp",
    [
        ("London", "18C"),
        ("Tokyo", "22C"),
    ],
)
def test_weather_bot_parameterized(
    city: str,
    expected_temp: str,
    tracereplay_session: TraceReplaySession,
) -> None:
    """Demonstrates parameterized tests with automatic distinct fixture naming."""
    req = RequestPayload(
        provider="openai",
        model="gpt-4o",
        prompt=f"Get forecast for {city}",
    )

    if tracereplay_session.mode == ReplayMode.RECORD:
        resp = ResponsePayload(content=f"Forecast for {city}: {expected_temp}, Clear skies.")
        assert tracereplay_session.recorder is not None
        tracereplay_session.recorder.record_interaction(req, resp)
        content = resp.content or ""
    else:
        assert tracereplay_session.replayer is not None
        resp = tracereplay_session.replayer.replay_interaction(req)
        content = resp.content or ""

    assert city in content
    assert expected_temp in content
