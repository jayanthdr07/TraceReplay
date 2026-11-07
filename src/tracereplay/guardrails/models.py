"""Data models and configurations for Token, Cost & Latency Guardrails."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GuardrailAction(str, Enum):
    """Action to take when a guardrail threshold or budget cap is breached."""

    RAISE = "raise"
    WARN = "warn"
    RECORD_ONLY = "record_only"


class GuardrailType(str, Enum):
    """Classification of guardrail metric and boundary checks."""

    TOTAL_TOKENS = "total_tokens"
    PROMPT_TOKENS = "prompt_tokens"
    COMPLETION_TOKENS = "completion_tokens"
    REQUEST_TOKENS = "request_tokens"
    TOTAL_COST = "total_cost"
    REQUEST_COST = "request_cost"
    TOTAL_LATENCY = "total_latency"
    REQUEST_LATENCY = "request_latency"


class GuardrailViolation(BaseModel):
    """Detailed record of a guardrail threshold breach."""

    model_config = ConfigDict(frozen=True)

    guardrail_type: GuardrailType
    threshold: float
    actual: float
    step_index: int
    model: str | None = None
    message: str
    timestamp: datetime = Field(default_factory=_utc_now)


class GuardrailConfig(BaseModel):
    """Configuration defining budget limits, latency constraints, and enforcement actions."""

    model_config = ConfigDict(frozen=True)

    # Token constraints (integers)
    max_tokens: int | None = Field(default=None, ge=1)
    max_prompt_tokens: int | None = Field(default=None, ge=1)
    max_completion_tokens: int | None = Field(default=None, ge=1)
    max_request_tokens: int | None = Field(default=None, ge=1)

    # Cost constraints in USD (floats)
    max_cost_usd: float | None = Field(default=None, ge=0.0)
    max_request_cost_usd: float | None = Field(default=None, ge=0.0)

    # Latency constraints in milliseconds (floats)
    max_latency_ms: float | None = Field(default=None, ge=0.0)
    max_request_latency_ms: float | None = Field(default=None, ge=0.0)

    # Behavior on violation
    action: GuardrailAction = GuardrailAction.RAISE

    # Model pricing overrides: model_name -> (prompt_cost_per_1m, completion_cost_per_1m)
    model_pricing: dict[str, tuple[float, float]] | None = None

    @property
    def is_configured(self) -> bool:
        """Return True if at least one guardrail cap is actively configured."""
        return any(
            v is not None
            for v in (
                self.max_tokens,
                self.max_prompt_tokens,
                self.max_completion_tokens,
                self.max_request_tokens,
                self.max_cost_usd,
                self.max_request_cost_usd,
                self.max_latency_ms,
                self.max_request_latency_ms,
            )
        )


class GuardrailReport(BaseModel):
    """Comprehensive evaluation report of all guardrail metrics and violations."""

    model_config = ConfigDict(frozen=True)

    passed: bool
    violations: list[GuardrailViolation] = Field(default_factory=list)
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0
    total_duration_ms: float = 0.0
    cost_breakdown_by_model: dict[str, float] = Field(default_factory=dict)
    tokens_by_model: dict[str, int] = Field(default_factory=dict)
    interaction_count: int = 0

    def summary_text(self) -> str:
        """Produce a formatted human-readable summary of the guardrail report."""
        status = "PASSED" if self.passed else "FAILED"
        lines = [
            f"=== Guardrail Report: {status} ===",
            f"Interactions: {self.interaction_count}",
            f"Total Tokens: {self.total_tokens:,} "
            f"(Prompt: {self.total_prompt_tokens:,}, Completion: {self.total_completion_tokens:,})",
            f"Total Cost: ${self.total_cost_usd:.5f} USD",
            f"Total Duration: {self.total_duration_ms:.1f}ms",
        ]
        if self.cost_breakdown_by_model:
            lines.append("Cost Breakdown by Model:")
            for m, c in sorted(self.cost_breakdown_by_model.items()):
                t = self.tokens_by_model.get(m, 0)
                lines.append(f"  - {m}: ${c:.5f} ({t:,} tokens)")
        if self.violations:
            lines.append(f"Violations ({len(self.violations)}):")
            for v in self.violations:
                lines.append(
                    f"  [Step {v.step_index}] {v.guardrail_type.value}: "
                    f"actual {v.actual:g} exceeded threshold {v.threshold:g}"
                )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to standard JSON-compatible dictionary."""
        return self.model_dump(mode="json")
