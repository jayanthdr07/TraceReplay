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


# ============================================================================
# Chaos Engineering Exceptions
# ============================================================================


class ChaosError(TraceReplayError):
    """Base exception for all faults injected by the TraceReplay AI Chaos Engine."""


class ChaosRateLimitError(ChaosError):
    """Raised when a 429 Rate Limit fault is injected."""

    def __init__(
        self,
        message: str = "Rate limit exceeded (429 Too Many Requests)",
        retry_after: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        extra = dict(details) if details else {}
        extra["status_code"] = 429
        if retry_after is not None:
            extra["retry_after"] = retry_after
        super().__init__(message, details=extra)
        self.status_code = 429
        self.retry_after = retry_after


class ChaosTimeoutError(ChaosError):
    """Raised when a simulated network timeout fault is injected."""

    def __init__(
        self,
        message: str = "Request timed out",
        duration_seconds: float = 0.0,
        details: dict[str, Any] | None = None,
    ) -> None:
        extra = dict(details) if details else {}
        if duration_seconds > 0:
            extra["duration_seconds"] = duration_seconds
        super().__init__(message, details=extra)
        self.duration_seconds = duration_seconds


class ChaosServerError(ChaosError):
    """Raised when a simulated HTTP 5xx server error is injected."""

    def __init__(
        self,
        message: str = "Internal server error (500)",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        extra = dict(details) if details else {}
        extra["status_code"] = status_code
        super().__init__(message, details=extra)
        self.status_code = status_code


class ChaosContextLengthError(ChaosError):
    """Raised when a simulated context window limit exceeded fault is injected."""

    def __init__(
        self,
        message: str = "Context window length exceeded",
        max_tokens: int = 8192,
        actual_tokens: int = 9500,
        details: dict[str, Any] | None = None,
    ) -> None:
        extra = dict(details) if details else {}
        extra["status_code"] = 400
        extra["max_tokens"] = max_tokens
        extra["actual_tokens"] = actual_tokens
        super().__init__(message, details=extra)
        self.status_code = 400
        self.max_tokens = max_tokens
        self.actual_tokens = actual_tokens


class ChaosMalformedOutputError(ChaosError):
    """Raised when an injected malformed output cannot be processed by the recipient."""


# ============================================================================
# Token, Cost & Latency Guardrail Exceptions
# ============================================================================


class BudgetExceededError(TraceReplayError):
    """Base exception for all token, financial cost, or latency budget breaches."""

    def __init__(
        self,
        message: str,
        metric: str,
        threshold: float,
        actual: float,
        details: dict[str, Any] | None = None,
    ) -> None:
        extra = dict(details) if details else {}
        extra["metric"] = metric
        extra["threshold"] = threshold
        extra["actual"] = actual
        super().__init__(message, details=extra)
        self.metric = metric
        self.threshold = threshold
        self.actual = actual


class TokenBudgetExceededError(BudgetExceededError):
    """Raised when an interaction or cumulative session exceeds allowable token caps."""

    def __init__(
        self,
        threshold: float,
        actual: float,
        token_type: str = "total_tokens",
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        msg = (
            message
            or f"Token budget exceeded for '{token_type}': actual {actual:g} tokens "
            f"exceeds limit of {threshold:g} tokens."
        )
        super().__init__(
            message=msg,
            metric=token_type,
            threshold=threshold,
            actual=actual,
            details=details,
        )


class CostBudgetExceededError(BudgetExceededError):
    """Raised when an interaction or cumulative session exceeds allowable financial cost in USD."""

    def __init__(
        self,
        threshold: float,
        actual: float,
        cost_type: str = "total_cost",
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        msg = (
            message
            or f"Cost budget exceeded for '{cost_type}': actual ${actual:.4f} "
            f"exceeds limit of ${threshold:.4f} USD."
        )
        super().__init__(
            message=msg,
            metric=cost_type,
            threshold=threshold,
            actual=actual,
            details=details,
        )


class LatencyBudgetExceededError(BudgetExceededError):
    """Raised when an interaction or cumulative session exceeds allowable latency limits."""

    def __init__(
        self,
        threshold: float,
        actual: float,
        latency_type: str = "latency_ms",
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        msg = (
            message
            or f"Latency budget exceeded for '{latency_type}': actual {actual:.1f}ms "
            f"exceeds limit of {threshold:.1f}ms."
        )
        super().__init__(
            message=msg,
            metric=latency_type,
            threshold=threshold,
            actual=actual,
            details=details,
        )
