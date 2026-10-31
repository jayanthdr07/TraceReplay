"""Unit tests for TraceReplay custom exception hierarchy."""

from __future__ import annotations

import pytest

from tracereplay.exceptions import (
    ConfigurationError,
    FixtureNotFoundError,
    InvalidFixtureError,
    LiveFallbackProhibitedError,
    RecordingError,
    RequestMismatchError,
    SequenceMismatchError,
    ToolExecutionError,
    TraceReplayError,
    UnsupportedOperationError,
)


def test_base_error_inheritance() -> None:
    #  Ensure all custom exceptions inherit from TraceReplayError.
    assert issubclass(ConfigurationError, TraceReplayError)
    assert issubclass(FixtureNotFoundError, TraceReplayError)
    assert issubclass(RequestMismatchError, TraceReplayError)
    assert issubclass(InvalidFixtureError, TraceReplayError)
    assert issubclass(LiveFallbackProhibitedError, TraceReplayError)
    assert issubclass(UnsupportedOperationError, TraceReplayError)
    assert issubclass(SequenceMismatchError, TraceReplayError)
    assert issubclass(RecordingError, TraceReplayError)
    assert issubclass(ToolExecutionError, TraceReplayError)


def test_error_message_and_details() -> None:
    # Ensure error messages and details are cleanly formatted.
    err = TraceReplayError("Something failed", details={"code": 404, "target": "test"})
    assert str(err) == "Something failed (code=404 | target='test')"
    assert err.details["code"] == 404


def test_fixture_not_found_error_properties() -> None:
    # verify FixtureNotFoundError preserves path and session name.
    err = FixtureNotFoundError(
        "Fixture missing",
        fixture_path="/path/to/fixture.json",
        session_name="test_checkout",
    )

    assert err.fixture_path == "/path/to/fixture.json"
    assert err.session_name == "test_checkout"
    assert "fixture_path='/path/to/fixture.json'" in str(err)


def test_request_mismatch_error_properties() -> None:
    """Verify RequestMismatchError preserves expected, actual, and diff."""
    err = RequestMismatchError(
        "Prompt does not match",
        expected={"model": "gpt-4o"},
        actual={"model": "gpt-3.5"},
        diff="- gpt-4o\n+ gpt-3.5",
        interaction_index=2,
    )
    assert err.expected == {"model": "gpt-4o"}
    assert err.actual == {"model": "gpt-3.5"}
    assert err.diff == "- gpt-4o\n+ gpt-3.5"
    assert err.interaction_index == 2


def test_sequence_mismatch_error_properties() -> None:
    """Verify SequenceMismatchError tracks expected vs actual indices."""
    err = SequenceMismatchError("Sequence diverged", expected_index=2, actual_index=3)
    assert err.expected_index == 2
    assert err.actual_index == 3
    assert "expected_index=2" in str(err)


def test_live_fallback_prohibited_error() -> None:
    """Ensure LiveFallbackProhibitedError can be raised cleanly."""
    with pytest.raises(LiveFallbackProhibitedError, match="Network calls disabled"):
        raise LiveFallbackProhibitedError("Network calls disabled in replay mode")
