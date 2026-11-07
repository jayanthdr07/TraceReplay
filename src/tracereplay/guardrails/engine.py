"""Guardrail enforcement engine tracking tokens, costs, and latencies in real time."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

from tracereplay.exceptions import (
    CostBudgetExceededError,
    LatencyBudgetExceededError,
    TokenBudgetExceededError,
)
from tracereplay.guardrails.models import (
    GuardrailAction,
    GuardrailConfig,
    GuardrailReport,
    GuardrailType,
    GuardrailViolation,
)
from tracereplay.guardrails.pricing import calculate_token_cost

if TYPE_CHECKING:
    from tracereplay.models import RequestPayload, ResponsePayload


class GuardrailEngine:
    """Monitors live and replayed interactions, enforcing token, cost, and latency budgets."""

    def __init__(self, config: GuardrailConfig) -> None:
        self.config = config
        self.accumulated_prompt_tokens: int = 0
        self.accumulated_completion_tokens: int = 0
        self.accumulated_total_tokens: int = 0
        self.accumulated_cost_usd: float = 0.0
        self.accumulated_duration_ms: float = 0.0
        self.cost_by_model: dict[str, float] = {}
        self.tokens_by_model: dict[str, int] = {}
        self.violations: list[GuardrailViolation] = []
        self.interaction_count: int = 0

    def evaluate_pre_request(self, request: RequestPayload, step_index: int) -> None:
        """Evaluate pre-call constraints before dispatching an LLM request."""
        # If total tokens or cost already exceeded a hard cap from prior steps:
        if self.config.max_tokens and self.accumulated_total_tokens >= self.config.max_tokens:
            msg = (
                f"Pre-request check failed at step {step_index}: cumulative tokens "
                f"({self.accumulated_total_tokens}) reached limit ({self.config.max_tokens})."
            )
            v = GuardrailViolation(
                guardrail_type=GuardrailType.TOTAL_TOKENS,
                threshold=float(self.config.max_tokens),
                actual=float(self.accumulated_total_tokens),
                step_index=step_index,
                model=request.model,
                message=msg,
            )
            self._handle_violation(v)

        if self.config.max_cost_usd and self.accumulated_cost_usd >= self.config.max_cost_usd:
            msg = (
                f"Pre-request check failed at step {step_index}: cumulative cost "
                f"(${self.accumulated_cost_usd:.4f}) already reached budget "
                f"(${self.config.max_cost_usd:.4f})."
            )
            v = GuardrailViolation(
                guardrail_type=GuardrailType.TOTAL_COST,
                threshold=float(self.config.max_cost_usd),
                actual=float(self.accumulated_cost_usd),
                step_index=step_index,
                model=request.model,
                message=msg,
            )
            self._handle_violation(v)

    def evaluate_post_response(
        self,
        request: RequestPayload,
        response: ResponsePayload,
        duration_ms: float,
        step_index: int,
    ) -> None:
        """Evaluate token, financial cost, and latency budgets following an LLM response."""
        p_tok = response.usage.prompt_tokens
        c_tok = response.usage.completion_tokens
        t_tok = response.usage.total_tokens or (p_tok + c_tok)

        step_cost = calculate_token_cost(
            model=request.model,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            custom_pricing=self.config.model_pricing,
        )

        # Update running aggregates
        self.accumulated_prompt_tokens += p_tok
        self.accumulated_completion_tokens += c_tok
        self.accumulated_total_tokens += t_tok
        self.accumulated_cost_usd = round(self.accumulated_cost_usd + step_cost, 6)
        self.accumulated_duration_ms = round(self.accumulated_duration_ms + duration_ms, 2)
        self.interaction_count += 1

        m_key = request.model
        self.tokens_by_model[m_key] = self.tokens_by_model.get(m_key, 0) + t_tok
        self.cost_by_model[m_key] = round(self.cost_by_model.get(m_key, 0.0) + step_cost, 6)

        # 1. Per-request token limit
        if self.config.max_request_tokens and t_tok > self.config.max_request_tokens:
            msg = (
                f"Step {step_index} tokens ({t_tok}) exceeded max_request_tokens "
                f"({self.config.max_request_tokens}) on model '{request.model}'."
            )
            self._handle_violation(
                GuardrailViolation(
                    guardrail_type=GuardrailType.REQUEST_TOKENS,
                    threshold=float(self.config.max_request_tokens),
                    actual=float(t_tok),
                    step_index=step_index,
                    model=request.model,
                    message=msg,
                )
            )

        # 2. Cumulative prompt tokens limit
        if (
            self.config.max_prompt_tokens
            and self.accumulated_prompt_tokens > self.config.max_prompt_tokens
        ):
            msg = (
                f"Cumulative prompt tokens ({self.accumulated_prompt_tokens}) exceeded "
                f"max_prompt_tokens ({self.config.max_prompt_tokens}) at step {step_index}."
            )
            self._handle_violation(
                GuardrailViolation(
                    guardrail_type=GuardrailType.PROMPT_TOKENS,
                    threshold=float(self.config.max_prompt_tokens),
                    actual=float(self.accumulated_prompt_tokens),
                    step_index=step_index,
                    model=request.model,
                    message=msg,
                )
            )

        # 3. Cumulative completion tokens limit
        if (
            self.config.max_completion_tokens
            and self.accumulated_completion_tokens > self.config.max_completion_tokens
        ):
            msg = (
                f"Cumulative completion tokens ({self.accumulated_completion_tokens}) exceeded "
                f"max_completion_tokens ({self.config.max_completion_tokens}) at step {step_index}."
            )
            self._handle_violation(
                GuardrailViolation(
                    guardrail_type=GuardrailType.COMPLETION_TOKENS,
                    threshold=float(self.config.max_completion_tokens),
                    actual=float(self.accumulated_completion_tokens),
                    step_index=step_index,
                    model=request.model,
                    message=msg,
                )
            )

        # 4. Cumulative total tokens limit
        if self.config.max_tokens and self.accumulated_total_tokens > self.config.max_tokens:
            msg = (
                f"Cumulative total tokens ({self.accumulated_total_tokens}) exceeded "
                f"max_tokens ({self.config.max_tokens}) at step {step_index}."
            )
            self._handle_violation(
                GuardrailViolation(
                    guardrail_type=GuardrailType.TOTAL_TOKENS,
                    threshold=float(self.config.max_tokens),
                    actual=float(self.accumulated_total_tokens),
                    step_index=step_index,
                    model=request.model,
                    message=msg,
                )
            )

        # 5. Per-request cost limit
        if self.config.max_request_cost_usd and step_cost > self.config.max_request_cost_usd:
            msg = (
                f"Step {step_index} cost (${step_cost:.4f}) exceeded max_request_cost_usd "
                f"(${self.config.max_request_cost_usd:.4f}) on model '{request.model}'."
            )
            self._handle_violation(
                GuardrailViolation(
                    guardrail_type=GuardrailType.REQUEST_COST,
                    threshold=float(self.config.max_request_cost_usd),
                    actual=float(step_cost),
                    step_index=step_index,
                    model=request.model,
                    message=msg,
                )
            )

        # 6. Cumulative cost limit
        if self.config.max_cost_usd and self.accumulated_cost_usd > self.config.max_cost_usd:
            msg = (
                f"Cumulative cost (${self.accumulated_cost_usd:.4f}) exceeded "
                f"max_cost_usd (${self.config.max_cost_usd:.4f}) at step {step_index}."
            )
            self._handle_violation(
                GuardrailViolation(
                    guardrail_type=GuardrailType.TOTAL_COST,
                    threshold=float(self.config.max_cost_usd),
                    actual=float(self.accumulated_cost_usd),
                    step_index=step_index,
                    model=request.model,
                    message=msg,
                )
            )

        # 7. Per-request latency limit
        if self.config.max_request_latency_ms and duration_ms > self.config.max_request_latency_ms:
            msg = (
                f"Step {step_index} latency ({duration_ms:.1f}ms) exceeded "
                f"max_request_latency_ms ({self.config.max_request_latency_ms:.1f}ms)."
            )
            self._handle_violation(
                GuardrailViolation(
                    guardrail_type=GuardrailType.REQUEST_LATENCY,
                    threshold=float(self.config.max_request_latency_ms),
                    actual=float(duration_ms),
                    step_index=step_index,
                    model=request.model,
                    message=msg,
                )
            )

        # 8. Cumulative latency limit
        if self.config.max_latency_ms and self.accumulated_duration_ms > self.config.max_latency_ms:
            msg = (
                f"Cumulative duration ({self.accumulated_duration_ms:.1f}ms) exceeded "
                f"max_latency_ms ({self.config.max_latency_ms:.1f}ms) at step {step_index}."
            )
            self._handle_violation(
                GuardrailViolation(
                    guardrail_type=GuardrailType.TOTAL_LATENCY,
                    threshold=float(self.config.max_latency_ms),
                    actual=float(self.accumulated_duration_ms),
                    step_index=step_index,
                    model=request.model,
                    message=msg,
                )
            )

    def evaluate_tool_execution(
        self,
        tool_name: str,
        duration_ms: float,
        step_index: int,
    ) -> None:
        """Evaluate duration budgets for local Python tool function invocations."""
        self.accumulated_duration_ms = round(self.accumulated_duration_ms + duration_ms, 2)

        if self.config.max_request_latency_ms and duration_ms > self.config.max_request_latency_ms:
            msg = (
                f"Tool '{tool_name}' latency ({duration_ms:.1f}ms) exceeded "
                f"max_request_latency_ms ({self.config.max_request_latency_ms:.1f}ms) "
                f"at step {step_index}."
            )
            self._handle_violation(
                GuardrailViolation(
                    guardrail_type=GuardrailType.REQUEST_LATENCY,
                    threshold=float(self.config.max_request_latency_ms),
                    actual=float(duration_ms),
                    step_index=step_index,
                    model=None,
                    message=msg,
                )
            )

        if self.config.max_latency_ms and self.accumulated_duration_ms > self.config.max_latency_ms:
            msg = (
                f"Cumulative duration ({self.accumulated_duration_ms:.1f}ms) exceeded "
                f"max_latency_ms ({self.config.max_latency_ms:.1f}ms) following tool '{tool_name}'."
            )
            self._handle_violation(
                GuardrailViolation(
                    guardrail_type=GuardrailType.TOTAL_LATENCY,
                    threshold=float(self.config.max_latency_ms),
                    actual=float(self.accumulated_duration_ms),
                    step_index=step_index,
                    model=None,
                    message=msg,
                )
            )

    def _handle_violation(self, violation: GuardrailViolation) -> None:
        """Process violation based on configured action (RAISE, WARN, RECORD_ONLY)."""
        self.violations.append(violation)

        if self.config.action == GuardrailAction.RAISE:
            if violation.guardrail_type in {
                GuardrailType.TOTAL_TOKENS,
                GuardrailType.PROMPT_TOKENS,
                GuardrailType.COMPLETION_TOKENS,
                GuardrailType.REQUEST_TOKENS,
            }:
                raise TokenBudgetExceededError(
                    threshold=violation.threshold,
                    actual=violation.actual,
                    token_type=violation.guardrail_type.value,
                    message=violation.message,
                )
            if violation.guardrail_type in {
                GuardrailType.TOTAL_COST,
                GuardrailType.REQUEST_COST,
            }:
                raise CostBudgetExceededError(
                    threshold=violation.threshold,
                    actual=violation.actual,
                    cost_type=violation.guardrail_type.value,
                    message=violation.message,
                )
            if violation.guardrail_type in {
                GuardrailType.TOTAL_LATENCY,
                GuardrailType.REQUEST_LATENCY,
            }:
                raise LatencyBudgetExceededError(
                    threshold=violation.threshold,
                    actual=violation.actual,
                    latency_type=violation.guardrail_type.value,
                    message=violation.message,
                )

        if self.config.action == GuardrailAction.WARN:
            warnings.warn(violation.message, UserWarning, stacklevel=3)

    def generate_report(self) -> GuardrailReport:
        """Generate a complete diagnostic snapshot of guardrail metrics and violations."""
        passed = len(self.violations) == 0 or self.config.action != GuardrailAction.RAISE
        return GuardrailReport(
            passed=passed,
            violations=list(self.violations),
            total_tokens=self.accumulated_total_tokens,
            total_prompt_tokens=self.accumulated_prompt_tokens,
            total_completion_tokens=self.accumulated_completion_tokens,
            total_cost_usd=round(self.accumulated_cost_usd, 5),
            total_duration_ms=round(self.accumulated_duration_ms, 2),
            cost_breakdown_by_model=dict(self.cost_by_model),
            tokens_by_model=dict(self.tokens_by_model),
            interaction_count=self.interaction_count,
        )
