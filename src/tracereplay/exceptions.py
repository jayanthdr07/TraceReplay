"""Custom Exception hierarchy for TraceReplay.

Every Exception provides structured attributes and clear debugging messages
to make diagnosing test failures, mismatches, and missing fixtures easier.
"""

from __future__ import annotations

from typing import Any


class TraceReplayError(Exception):
    """Base exception for all TraceReplay runtime errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            detail_str = " | ".join(f"{k}={v!r}" for k, v in sorted(self.details.items()))
            return f"{self.message} ({detail_str})"
        return self.message


class ConfigurationError(TraceReplayError):
    """Raised when configuration values or environment variables are invalid."""


class FixtureNotFoundError(TraceReplayError):
    """Raised in Replay Mode when a requested fixture file or session does not exist."""

    def __init__(
        self,
        message: str,
        fixture_path: str | None = None,
        session_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        extra = dict(details) if details else {}
        if fixture_path:
            extra["fixture_path"] = fixture_path
        if session_name:
            extra["session_name"] = session_name
        super().__init__(message, details=extra)
        self.fixture_path = fixture_path
        self.session_name = session_name


class RequestMismatchError(TraceReplayError):
    """Raised in Replay Mode when an incoming request does not match the recorded interaction."""

    def __init__(
        self,
        message: str,
        expected: dict[str, Any] | None = None,
        actual: dict[str, Any] | None = None,
        diff: str | None = None,
        interaction_index: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        extra = dict(details) if details else {}
        if interaction_index is not None:
            extra["interaction_index"] = interaction_index
        super().__init__(message, details=extra)
        self.expected = expected or {}
        self.actual = actual or {}
        self.diff = diff
        self.interaction_index = interaction_index


class InvalidFixtureError(TraceReplayError):
    """Raised when a fixture file contains malformed JSON or fails schema validation."""

    def __init__(
        self,
        message: str,
        fixture_path: str | None = None,
        validation_error: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        extra = dict(details) if details else {}
        if fixture_path:
            extra["fixture_path"] = fixture_path
        if validation_error:
            extra["validation_error"] = validation_error
        super().__init__(message, details=extra)
        self.fixture_path = fixture_path
        self.validation_error = validation_error


class LiveFallbackProhibitedError(TraceReplayError):
    """Raised when replay mode attempts to reach the live network.

    This exception enforces the core Zero-Live-Fallback Guarantee of TraceReplay:
    tests running in Replay Mode must NEVER silently incur live API costs.
    """


class UnsupportedOperationError(TraceReplayError):
    """Raised when an operation or provider feature is not currently supported."""


class SequenceMismatchError(TraceReplayError):
    """Raised when interactions occur in a different order than was recorded."""

    def __init__(
        self,
        message: str,
        expected_index: int,
        actual_index: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        extra = dict(details) if details else {}
        extra["expected_index"] = expected_index
        extra["actual_index"] = actual_index
        super().__init__(message, details=extra)
        self.expected_index = expected_index
        self.actual_index = actual_index


class RecordingError(TraceReplayError):
    """Raised when live recording fails during interception or fixture capture."""


class ToolExecutionError(TraceReplayError):
    """Raised when a tool execution record fails or tool outputs cannot be replayed."""
