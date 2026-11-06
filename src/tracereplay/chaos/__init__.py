"""AI Chaos Engineering and Fault Injection engine for TraceReplay.

Allows developers to test LLM agent resilience, exponential backoffs, and
error handling paths deterministically by simulating 429 Rate Limits,
Network Timeouts, 5xx Server Errors, Context Window Limits, Malformed JSON,
and Hallucinated Tool Calls.
"""

from __future__ import annotations

from typing import Any

from tracereplay.chaos.engine import ChaosEngine
from tracereplay.chaos.models import ChaosConfig, Fault, FaultRecord, FaultType


def rate_limit(
    step: int | None = None,
    tool: str | None = None,
    retry_after: float | None = None,
    max_times: int = 1,
    native: bool = True,
    message: str | None = None,
) -> Fault:
    """Inject a 429 Rate Limit error into LLM requests or tool calls."""
    return Fault(
        fault_type=FaultType.RATE_LIMIT,
        step=step,
        tool=tool,
        retry_after=retry_after,
        max_times=max_times,
        native=native,
        status_code=429,
        message=message or "Rate limit exceeded (429 Too Many Requests)",
    )


def timeout(
    step: int | None = None,
    tool: str | None = None,
    duration_seconds: float = 0.0,
    max_times: int = 1,
    native: bool = True,
    message: str | None = None,
) -> Fault:
    """Inject a network or API timeout error."""
    return Fault(
        fault_type=FaultType.TIMEOUT,
        step=step,
        tool=tool,
        duration_seconds=duration_seconds,
        max_times=max_times,
        native=native,
        message=message or "Request timed out",
    )


def server_error(
    status_code: int = 500,
    step: int | None = None,
    tool: str | None = None,
    max_times: int = 1,
    native: bool = True,
    message: str | None = None,
) -> Fault:
    """Inject an HTTP 5xx Internal Server Error (500, 502, 503, 504)."""
    return Fault(
        fault_type=FaultType.SERVER_ERROR,
        status_code=status_code,
        step=step,
        tool=tool,
        max_times=max_times,
        native=native,
        message=message or f"Internal server error ({status_code})",
    )


def context_length_exceeded(
    step: int | None = None,
    max_tokens: int = 8192,
    actual_tokens: int = 9500,
    max_times: int = 1,
    native: bool = True,
    message: str | None = None,
) -> Fault:
    """Inject a Context Window Exceeded error."""
    msg = (
        message
        or f"This model's maximum context length is {max_tokens} tokens. "
        f"However, your request resulted in {actual_tokens} tokens."
    )
    return Fault(
        fault_type=FaultType.CONTEXT_LENGTH,
        step=step,
        max_times=max_times,
        native=native,
        status_code=400,
        message=msg,
    )


def malformed_json(
    step: int | None = None,
    corrupted_output: str | None = None,
    max_times: int = 1,
) -> Fault:
    """Inject a malformed / unparsable JSON response string to test error recovery."""
    return Fault(
        fault_type=FaultType.MALFORMED_JSON,
        step=step,
        corrupted_output=corrupted_output or '{"status": "partial", "items": [',
        max_times=max_times,
    )


def hallucinated_tool(
    tool_name: str = "undefined_action_executor",
    arguments: dict[str, Any] | None = None,
    step: int | None = None,
    max_times: int = 1,
) -> Fault:
    """Inject a response containing a hallucinated or unregistered tool call."""
    return Fault(
        fault_type=FaultType.HALLUCINATED_TOOL,
        step=step,
        hallucinated_tool_name=tool_name,
        hallucinated_arguments=arguments or {"cmd": "rm -rf /", "force": True},
        max_times=max_times,
    )


def content_filter(
    step: int | None = None,
    refusal_text: str | None = None,
    max_times: int = 1,
) -> Fault:
    """Inject a content filter / safety refusal response."""
    return Fault(
        fault_type=FaultType.CONTENT_FILTER,
        step=step,
        refusal_text=refusal_text or "The request was refused by content safety policies.",
        max_times=max_times,
    )


def latency(
    delay_ms: float = 500.0,
    step: int | None = None,
    tool: str | None = None,
    max_times: int = 1,
) -> Fault:
    """Inject an artificial latency delay (in milliseconds)."""
    return Fault(
        fault_type=FaultType.LATENCY,
        step=step,
        tool=tool,
        delay_ms=delay_ms,
        max_times=max_times,
    )


def custom(
    exception: Any,
    step: int | None = None,
    tool: str | None = None,
    max_times: int = 1,
) -> Fault:
    """Inject an arbitrary custom exception or exception class."""
    return Fault(
        fault_type=FaultType.CUSTOM,
        step=step,
        tool=tool,
        custom_exception=exception,
        max_times=max_times,
    )


__all__ = [
    "ChaosEngine",
    "ChaosConfig",
    "Fault",
    "FaultRecord",
    "FaultType",
    "rate_limit",
    "timeout",
    "server_error",
    "context_length_exceeded",
    "malformed_json",
    "hallucinated_tool",
    "content_filter",
    "latency",
    "custom",
]
