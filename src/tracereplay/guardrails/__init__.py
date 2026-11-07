"""TraceReplay Guardrails: Token, Cost & Latency budget enforcers and hard stop guards."""

from __future__ import annotations

from tracereplay.guardrails.engine import GuardrailEngine
from tracereplay.guardrails.models import (
    GuardrailAction,
    GuardrailConfig,
    GuardrailReport,
    GuardrailType,
    GuardrailViolation,
)
from tracereplay.guardrails.pricing import (
    STANDARD_MODEL_PRICING,
    calculate_token_cost,
    normalize_model_identifier,
)


def token_budget(
    max_tokens: int | None = None,
    max_prompt_tokens: int | None = None,
    max_completion_tokens: int | None = None,
    max_request_tokens: int | None = None,
    action: GuardrailAction = GuardrailAction.RAISE,
) -> GuardrailConfig:
    """Convenience helper to configure token budget caps."""
    return GuardrailConfig(
        max_tokens=max_tokens,
        max_prompt_tokens=max_prompt_tokens,
        max_completion_tokens=max_completion_tokens,
        max_request_tokens=max_request_tokens,
        action=action,
    )


def cost_budget(
    max_cost_usd: float | None = None,
    max_request_cost_usd: float | None = None,
    model_pricing: dict[str, tuple[float, float]] | None = None,
    action: GuardrailAction = GuardrailAction.RAISE,
) -> GuardrailConfig:
    """Convenience helper to configure financial cost budget caps in USD."""
    return GuardrailConfig(
        max_cost_usd=max_cost_usd,
        max_request_cost_usd=max_request_cost_usd,
        model_pricing=model_pricing,
        action=action,
    )


def latency_budget(
    max_latency_ms: float | None = None,
    max_request_latency_ms: float | None = None,
    action: GuardrailAction = GuardrailAction.RAISE,
) -> GuardrailConfig:
    """Convenience helper to configure latency and execution duration caps."""
    return GuardrailConfig(
        max_latency_ms=max_latency_ms,
        max_request_latency_ms=max_request_latency_ms,
        action=action,
    )


__all__ = [
    "GuardrailAction",
    "GuardrailConfig",
    "GuardrailEngine",
    "GuardrailReport",
    "GuardrailType",
    "GuardrailViolation",
    "STANDARD_MODEL_PRICING",
    "calculate_token_cost",
    "cost_budget",
    "latency_budget",
    "normalize_model_identifier",
    "token_budget",
]
