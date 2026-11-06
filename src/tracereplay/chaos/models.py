"""Data models, enums, and configurations for AI Chaos Engineering."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FaultType(str, Enum):
    """Categorization of simulated AI infrastructure and behavioral faults."""

    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    SERVER_ERROR = "server_error"
    CONTEXT_LENGTH = "context_length"
    MALFORMED_JSON = "malformed_json"
    HALLUCINATED_TOOL = "hallucinated_tool"
    CONTENT_FILTER = "content_filter"
    LATENCY = "latency"
    CUSTOM = "custom"


class Fault(BaseModel):
    """Declarative definition of an AI fault injection scenario."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    fault_type: FaultType
    step: int | None = None
    tool: str | None = None
    probability: float | None = Field(default=None, ge=0.0, le=1.0)
    max_times: int = Field(default=1, ge=0)  # 0 means unlimited
    status_code: int = 429
    retry_after: float | None = None
    duration_seconds: float = 0.0
    delay_ms: float = 0.0
    corrupted_output: str | None = None
    hallucinated_tool_name: str | None = None
    hallucinated_arguments: dict[str, Any] | None = None
    refusal_text: str | None = None
    message: str | None = None
    native: bool = True
    custom_exception: Any = None
    _trigger_count: int = 0

    @property
    def trigger_count(self) -> int:
        """Return the number of times this fault has triggered so far."""
        return self._trigger_count

    def increment_trigger(self) -> None:
        """Record an execution trigger of this fault."""
        self._trigger_count += 1

    def is_exhausted(self) -> bool:
        """Return True if this fault has reached its maximum execution count."""
        return self.max_times > 0 and self._trigger_count >= self.max_times


class FaultRecord(BaseModel):
    """Immutable audit record of a triggered chaos fault during test execution."""

    model_config = ConfigDict(frozen=True)

    fault_type: FaultType
    step: int | None = None
    tool: str | None = None
    action_taken: str
    message: str | None = None
    timestamp: datetime = Field(default_factory=_utc_now)


class ChaosConfig(BaseModel):
    """Global configuration governing AI Chaos Engineering for a test session."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    faults: list[Fault] = Field(default_factory=list)
    rate_limit_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    timeout_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    latency_jitter_range_ms: tuple[float, float] | None = None
    seed: int | None = None
