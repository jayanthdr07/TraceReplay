"""Unit tests for Deterministic Clock & Freeze Time (Feature 5)."""

from __future__ import annotations

import contextlib
import datetime
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tracereplay.clock import (
    DeterministicClock,
    freeze_time,
    parse_datetime_input,
)
from tracereplay.config import TraceReplayConfig
from tracereplay.core.session import TraceReplaySession
from tracereplay.models import (
    Interaction,
    ReplayMode,
    RequestPayload,
    ResponsePayload,
    SessionRecord,
)
from tracereplay.storage.json_storage import JsonStorageEngine


def test_parse_datetime_input_formats() -> None:
    """Verify parser handles strings, dates, datetimes, and timestamps."""
    # 1. ISO string with Z
    dt1 = parse_datetime_input("2026-11-07T10:00:00Z")
    assert dt1.year == 2026
    assert dt1.month == 11
    assert dt1.day == 7
    assert dt1.hour == 10
    assert dt1.tzinfo == datetime.timezone.utc

    # 2. String with space and UTC
    dt2 = parse_datetime_input("2026-11-07 14:30:00 UTC")
    assert dt2.hour == 14
    assert dt2.minute == 30

    # 3. Date only
    dt3 = parse_datetime_input("2026-11-07")
    assert dt3.year == 2026
    assert dt3.hour == 0

    # 4. datetime.date object
    d = datetime.date(2026, 12, 25)
    dt4 = parse_datetime_input(d)
    assert dt4.year == 2026
    assert dt4.month == 12
    assert dt4.day == 25

    # 5. Numeric timestamp
    dt5 = parse_datetime_input(1762509600)
    assert dt5.tzinfo == datetime.timezone.utc

    # 6. Errors
    with pytest.raises(ValueError, match="Cannot parse datetime"):
        parse_datetime_input("invalid-date-string")

    with pytest.raises(TypeError, match="Unsupported datetime input type"):
        parse_datetime_input([2026, 11, 7])  # type: ignore[arg-type]


def test_deterministic_clock_now_and_utcnow() -> None:
    """Verify now(), utcnow(), and today() reflect the frozen target time."""
    target_str = "2026-11-07T10:00:00Z"
    clock = DeterministicClock(target_time=target_str)

    with clock:
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        assert now_dt.year == 2026
        assert now_dt.month == 11
        assert now_dt.day == 7
        assert now_dt.hour == 10

        utc_dt = datetime.datetime.utcnow()
        assert utc_dt.year == 2026
        assert utc_dt.hour == 10
        assert utc_dt.tzinfo is None  # utcnow is naive in standard library

        today = datetime.date.today()
        assert today.year == 2026
        assert today.month == 11
        assert today.day == 7


def test_deterministic_clock_time_and_monotonic() -> None:
    """Verify time.time() and time.monotonic() return simulated readings."""
    target_str = "2026-11-07T10:00:00Z"
    target_dt = parse_datetime_input(target_str)
    clock = DeterministicClock(target_time=target_str)

    with clock:
        posix_time = time.time()
        assert posix_time == pytest.approx(target_dt.timestamp(), rel=1e-5)

        mono_1 = time.monotonic()
        clock.advance(seconds=15)
        mono_2 = time.monotonic()
        assert mono_2 - mono_1 == pytest.approx(15.0)


def test_deterministic_clock_advance_and_tick() -> None:
    """Verify manual clock advancement changes the reported time."""
    clock = DeterministicClock(target_time="2026-11-07T10:00:00Z")

    with clock:
        assert datetime.datetime.utcnow().minute == 0
        clock.advance(seconds=120)
        assert datetime.datetime.utcnow().minute == 2

        clock.tick(seconds=30)
        assert datetime.datetime.utcnow().second == 30

        clock.set_time("2026-12-01T00:00:00Z")
        assert datetime.datetime.utcnow().month == 12
        assert datetime.datetime.utcnow().day == 1


def test_deterministic_clock_simulates_sleep_without_delay() -> None:
    """Verify time.sleep advances the mock clock instantly without real blocking delays."""
    clock = DeterministicClock(target_time="2026-11-07T10:00:00Z")

    start_wall = time.perf_counter()
    with clock:
        assert datetime.datetime.utcnow().minute == 0

        # Simulate sleeping for 300 seconds (5 minutes)
        time.sleep(300.0)

        # Simulated monotonic advanced by 300 seconds
        assert clock.monotonic() - clock.state.initial_monotonic == pytest.approx(300.0)
        # Simulated time jumped forward 5 minutes
        assert datetime.datetime.utcnow().minute == 5
        assert clock.state.sleep_calls == [300.0]

    elapsed_wall = time.perf_counter() - start_wall
    # Real elapsed wall time was instantaneous (< 0.2s) rather than 300s
    assert elapsed_wall < 0.2


def test_freeze_time_context_manager_lifecycle() -> None:
    """Verify freeze_time context manager activates and unpatches cleanly."""
    real_year = datetime.datetime.now().year

    with freeze_time("2026-11-07T10:00:00Z"):
        assert datetime.datetime.now(datetime.timezone.utc).year == 2026

    # Restored after context exit
    assert datetime.datetime.now().year == real_year


def test_freeze_time_sync_decorator() -> None:
    """Verify freeze_time works as a function decorator on sync functions."""

    @freeze_time("2026-11-07T10:00:00Z")
    def run_agent_task() -> int:
        return datetime.datetime.now(datetime.timezone.utc).year

    assert run_agent_task() == 2026


@pytest.mark.asyncio
async def test_freeze_time_async_decorator() -> None:
    """Verify freeze_time works as a decorator on asynchronous coroutines."""

    @freeze_time("2026-11-07T10:00:00Z")
    async def arun_agent_task() -> int:
        return datetime.datetime.now(datetime.timezone.utc).year

    result = await arun_agent_task()
    assert result == 2026


def test_trace_replay_session_explicit_freeze_time() -> None:
    """Verify TraceReplaySession freezes clock when freeze_time parameter is passed."""
    with TraceReplaySession(
        name="test_freeze_sess",
        mode=ReplayMode.PASSTHROUGH,
        freeze_time="2026-11-07T10:00:00Z",
    ) as sess:
        assert sess.is_time_frozen is True
        assert sess.clock is not None
        assert datetime.datetime.now(datetime.timezone.utc).year == 2026
        assert datetime.datetime.now(datetime.timezone.utc).month == 11

    assert sess.is_time_frozen is False


def test_trace_replay_session_auto_freeze_to_fixture() -> None:
    """Verify TraceReplaySession in REPLAY mode auto-freezes to fixture's recorded timestamp."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = TraceReplayConfig(fixtures_dir=Path(tmp_dir), mode=ReplayMode.REPLAY)
        storage = JsonStorageEngine(config=cfg)

        recorded_time = datetime.datetime(2026, 11, 7, 8, 30, 0, tzinfo=datetime.timezone.utc)
        session_rec = SessionRecord(
            name="agent_auto_freeze",
            created_at=recorded_time,
            interactions=[
                Interaction(
                    session_id="s1",
                    index=0,
                    timestamp=recorded_time,
                    request=RequestPayload(provider="openai", model="gpt-4o", prompt="What time?"),
                    response=ResponsePayload(content="8:30 AM"),
                )
            ],
        )
        storage.save(session_rec)

        # Replay with freeze_time=True (auto-sync to fixture)
        with TraceReplaySession(
            name="agent_auto_freeze",
            mode=ReplayMode.REPLAY,
            config=cfg,
            freeze_time=True,
        ) as sess:
            assert sess.is_time_frozen is True
            cur = datetime.datetime.now(datetime.timezone.utc)
            assert cur.year == 2026
            assert cur.month == 11
            assert cur.hour == 8
            assert cur.minute == 30

        assert sess.is_time_frozen is False


def test_pytest_marker_freeze_time_resolution() -> None:
    """Verify pytest marker resolves freeze_time parameter into session."""
    from tracereplay.pytest_plugin import create_tracereplay_session

    req = MagicMock(spec=pytest.FixtureRequest)
    req.config.getoption.return_value = False
    req.node.module.__name__ = "test_mod"
    req.node.name = "test_clock_plugin"
    del req.node.callspec

    class DummyMarker:
        kwargs = {
            "fixture": "custom_clock_fixture",
            "mode": "replay",
            "freeze_time": "2026-11-07T12:00:00Z",
        }
        args = ()

    req.node.get_closest_marker.return_value = DummyMarker()

    cfg = TraceReplayConfig()
    generator = create_tracereplay_session(req, cfg)
    sess = next(generator)

    assert sess.name == "custom_clock_fixture"
    assert sess.clock is not None
    assert sess.clock_config is not None

    with contextlib.suppress(StopIteration):
        next(generator)


def test_clock_state_serialization() -> None:
    """Verify ClockState to_dict() produces valid dictionary."""
    clock = DeterministicClock(target_time="2026-11-07T10:00:00Z")
    clock.sleep(5.0)

    data = clock.state.to_dict()
    assert "2026-11-07" in data["initial_time"]
    assert data["total_advanced_seconds"] == 5.0
    assert data["sleep_calls_count"] == 1
    assert data["total_slept_seconds"] == 5.0
