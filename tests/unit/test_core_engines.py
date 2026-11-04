"""Unit tests for the recording, replay, and session execution engines."""

from __future__ import annotations

from pathlib import Path

import pytest

from tracereplay.config import TraceReplayConfig
from tracereplay.core import get_current_session, session
from tracereplay.exceptions import FixtureNotFoundError, RequestMismatchError
from tracereplay.models import (
    ReplayMode,
    RequestPayload,
    ResponsePayload,
    TokenUsage,
)


def test_session_context_management(tmp_path: Path) -> None:
    """Verify context manager enters, sets active session, and cleans up on exit."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    assert get_current_session() is None

    with session("test_ctx", mode=ReplayMode.PASSTHROUGH, config=cfg) as sess:
        assert get_current_session() is sess
        assert sess.mode == ReplayMode.PASSTHROUGH

    assert get_current_session() is None


def test_record_and_replay_roundtrip(tmp_path: Path) -> None:
    """End-to-end verification of recording an interaction and replaying it offline."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    session_name = "test_roundtrip"

    req = RequestPayload(
        provider="openai",
        model="gpt-4o",
        messages=[{"role": "user", "content": "What is the capital of France?"}],
    )
    resp = ResponsePayload(
        content="The capital of France is Paris.",
        usage=TokenUsage(prompt_tokens=10, completion_tokens=8, total_tokens=18),
    )

    # 1. Record Mode
    with session(session_name, mode=ReplayMode.RECORD, config=cfg) as sess:
        assert sess.recorder is not None
        interaction = sess.recorder.record_interaction(req, resp, duration_ms=120.5)
        assert interaction.index == 0
        assert interaction.duration_ms == 120.5

    # Verify fixture was written to disk
    fixture_file = tmp_path / f"{session_name}.json"
    assert fixture_file.exists()

    # 2. Replay Mode
    with session(session_name, mode=ReplayMode.REPLAY, config=cfg) as sess:
        assert sess.replayer is not None
        replayed_resp = sess.replayer.replay_interaction(req)
        assert replayed_resp.content == "The capital of France is Paris."
        assert replayed_resp.usage.total_tokens == 18


def test_replay_missing_fixture_raises_fixture_not_found(tmp_path: Path) -> None:
    """Verify zero-live-fallback: missing fixture raises FixtureNotFoundError."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    with session("nonexistent_session", mode=ReplayMode.REPLAY, config=cfg) as sess:
        assert sess.replayer is not None
        req = RequestPayload(provider="openai", model="gpt-4o", prompt="Hi")
        with pytest.raises(FixtureNotFoundError):
            sess.replayer.replay_interaction(req)


def test_replay_request_mismatch_raises_informative_error(tmp_path: Path) -> None:
    """Verify request discrepancy raises RequestMismatchError with visual diff."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    session_name = "test_mismatch"

    recorded_req = RequestPayload(provider="openai", model="gpt-4o", prompt="Hello")
    resp = ResponsePayload(content="World")

    with session(session_name, mode=ReplayMode.RECORD, config=cfg) as sess:
        assert sess.recorder is not None
        sess.recorder.record_interaction(recorded_req, resp)

    different_req = RequestPayload(provider="openai", model="gpt-4o", prompt="Goodbye")

    with session(session_name, mode=ReplayMode.REPLAY, config=cfg) as sess:
        assert sess.replayer is not None
        with pytest.raises(RequestMismatchError) as exc_info:
            sess.replayer.replay_interaction(different_req)

        err_str = str(exc_info.value)
        assert "Request mismatch in session 'test_mismatch'" in err_str
        assert "Prompt text does not match" in err_str
        assert exc_info.value.diff is not None


@pytest.mark.asyncio
async def test_async_session_and_replayer(tmp_path: Path) -> None:
    """Verify async context manager and areplay_interaction execution."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    session_name = "test_async"

    req = RequestPayload(provider="openai", model="gpt-4o", prompt="Async query")
    resp = ResponsePayload(content="Async reply")

    async with session(session_name, mode=ReplayMode.RECORD, config=cfg) as sess:
        assert sess.recorder is not None
        sess.recorder.record_interaction(req, resp)

    async with session(session_name, mode=ReplayMode.REPLAY, config=cfg) as sess:
        assert sess.replayer is not None
        replayed = await sess.replayer.areplay_interaction(req)
        assert replayed.content == "Async reply"
