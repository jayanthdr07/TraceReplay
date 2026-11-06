"""Chaos Engine orchestrating fault selection, exception synthesis, and response corruption."""

from __future__ import annotations

import asyncio
import random
import time
from typing import TYPE_CHECKING, Any, cast

from tracereplay.chaos.models import ChaosConfig, Fault, FaultRecord, FaultType
from tracereplay.chaos.native import build_native_provider_exception
from tracereplay.exceptions import (
    ChaosContextLengthError,
    ChaosRateLimitError,
    ChaosServerError,
    ChaosTimeoutError,
)
from tracereplay.models import RequestPayload, ResponsePayload, ToolCallRecord

if TYPE_CHECKING:
    from tracereplay.providers.base import BaseProviderAdapter


class ChaosEngine:
    """Evaluates and executes active chaos fault injection rules during test execution."""

    def __init__(self, config: ChaosConfig | None = None) -> None:
        self.config = config or ChaosConfig()
        self.history: list[FaultRecord] = []
        self._rng = random.Random(self.config.seed) if self.config.seed is not None else random

    def _find_matching_request_fault(self, step_index: int) -> Fault | None:
        """Find the first active fault matching the current request step index."""
        for fault in self.config.faults:
            if fault.is_exhausted():
                continue

            # Must not be a tool-only fault
            if fault.tool is not None and fault.step is None:
                continue

            if fault.step is not None and fault.step != step_index:
                continue

            if fault.probability is not None and self._rng.random() > fault.probability:
                continue

            return fault

        # Check global probabilistic faults
        if (
            self.config.rate_limit_probability > 0.0
            and self._rng.random() < self.config.rate_limit_probability
        ):
            return Fault(
                fault_type=FaultType.RATE_LIMIT,
                step=step_index,
                max_times=1,
                status_code=429,
            )

        if (
            self.config.timeout_probability > 0.0
            and self._rng.random() < self.config.timeout_probability
        ):
            return Fault(
                fault_type=FaultType.TIMEOUT,
                step=step_index,
                max_times=1,
            )

        return None

    def _find_matching_tool_fault(self, tool_name: str, step_index: int) -> Fault | None:
        """Find the first active fault matching the designated tool execution."""
        for fault in self.config.faults:
            if fault.is_exhausted():
                continue

            if fault.tool is not None and fault.tool != tool_name:
                continue

            if fault.step is not None and fault.step != step_index:
                continue

            if fault.probability is not None and self._rng.random() > fault.probability:
                continue

            return fault

        return None

    def evaluate_pre_request(
        self,
        adapter: BaseProviderAdapter,
        request: RequestPayload,
        step_index: int,
    ) -> Any:
        """Synchronously evaluate and execute a fault before dispatching an LLM request.

        Returns a synthetic corrupted response object if the fault mutates output,
        None if execution should proceed normally (e.g. after latency jitter),
        or raises the target simulated exception.
        """
        # Global latency jitter
        if self.config.latency_jitter_range_ms:
            low, high = self.config.latency_jitter_range_ms
            delay = self._rng.uniform(low, high)
            if delay > 0:
                time.sleep(delay / 1000.0)

        fault = self._find_matching_request_fault(step_index)
        if fault is None:
            return None

        fault.increment_trigger()

        # 1. Latency injection
        if fault.fault_type == FaultType.LATENCY:
            if fault.delay_ms > 0:
                time.sleep(fault.delay_ms / 1000.0)
            self.history.append(
                FaultRecord(
                    fault_type=fault.fault_type,
                    step=step_index,
                    action_taken=f"delayed_{fault.delay_ms}ms",
                    message=fault.message,
                )
            )
            return None

        # 2. Response mutations (synthetic response reconstruction)
        if fault.fault_type in {
            FaultType.MALFORMED_JSON,
            FaultType.HALLUCINATED_TOOL,
            FaultType.CONTENT_FILTER,
        }:
            synthetic_payload = self._build_mutated_payload(fault)
            self.history.append(
                FaultRecord(
                    fault_type=fault.fault_type,
                    step=step_index,
                    action_taken="returned_corrupted_response",
                    message=fault.message,
                )
            )
            return adapter.build_replayed_response(synthetic_payload, request)

        # 3. Exceptions
        if fault.duration_seconds > 0 and fault.fault_type == FaultType.TIMEOUT:
            time.sleep(fault.duration_seconds)

        exc = self._synthesize_exception(fault, adapter)
        self.history.append(
            FaultRecord(
                fault_type=fault.fault_type,
                step=step_index,
                action_taken=f"raised_{type(exc).__name__}",
                message=str(exc),
            )
        )
        raise exc

    async def aevaluate_pre_request(
        self,
        adapter: BaseProviderAdapter,
        request: RequestPayload,
        step_index: int,
    ) -> Any:
        """Asynchronously evaluate and execute a fault before dispatching an LLM request."""
        # Global latency jitter
        if self.config.latency_jitter_range_ms:
            low, high = self.config.latency_jitter_range_ms
            delay = self._rng.uniform(low, high)
            if delay > 0:
                await asyncio.sleep(delay / 1000.0)

        fault = self._find_matching_request_fault(step_index)
        if fault is None:
            return None

        fault.increment_trigger()

        # 1. Latency injection
        if fault.fault_type == FaultType.LATENCY:
            if fault.delay_ms > 0:
                await asyncio.sleep(fault.delay_ms / 1000.0)
            self.history.append(
                FaultRecord(
                    fault_type=fault.fault_type,
                    step=step_index,
                    action_taken=f"delayed_{fault.delay_ms}ms",
                    message=fault.message,
                )
            )
            return None

        # 2. Response mutations
        if fault.fault_type in {
            FaultType.MALFORMED_JSON,
            FaultType.HALLUCINATED_TOOL,
            FaultType.CONTENT_FILTER,
        }:
            synthetic_payload = self._build_mutated_payload(fault)
            self.history.append(
                FaultRecord(
                    fault_type=fault.fault_type,
                    step=step_index,
                    action_taken="returned_corrupted_response",
                    message=fault.message,
                )
            )
            return adapter.build_replayed_response(synthetic_payload, request)

        # 3. Exceptions
        if fault.duration_seconds > 0 and fault.fault_type == FaultType.TIMEOUT:
            await asyncio.sleep(fault.duration_seconds)

        exc = self._synthesize_exception(fault, adapter)
        self.history.append(
            FaultRecord(
                fault_type=fault.fault_type,
                step=step_index,
                action_taken=f"raised_{type(exc).__name__}",
                message=str(exc),
            )
        )
        raise exc

    def evaluate_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],  # noqa: ARG002
        step_index: int,
    ) -> None:
        """Evaluate and inject faults into local Python tool function executions."""
        fault = self._find_matching_tool_fault(tool_name, step_index)
        if fault is None:
            return

        fault.increment_trigger()

        if fault.fault_type == FaultType.LATENCY:
            if fault.delay_ms > 0:
                time.sleep(fault.delay_ms / 1000.0)
            self.history.append(
                FaultRecord(
                    fault_type=fault.fault_type,
                    tool=tool_name,
                    step=step_index,
                    action_taken=f"delayed_{fault.delay_ms}ms",
                    message=fault.message,
                )
            )
            return

        if fault.fault_type == FaultType.TIMEOUT:
            if fault.duration_seconds > 0:
                time.sleep(fault.duration_seconds)
            timeout_exc = ChaosTimeoutError(
                message=fault.message or f"Tool '{tool_name}' timed out.",
                duration_seconds=fault.duration_seconds,
            )
            self.history.append(
                FaultRecord(
                    fault_type=fault.fault_type,
                    tool=tool_name,
                    step=step_index,
                    action_taken="raised_ChaosTimeoutError",
                    message=str(timeout_exc),
                )
            )
            raise timeout_exc

        if fault.custom_exception is not None:
            custom_exc: Exception = (
                fault.custom_exception()
                if isinstance(fault.custom_exception, type)
                else fault.custom_exception
            )
            self.history.append(
                FaultRecord(
                    fault_type=fault.fault_type,
                    tool=tool_name,
                    step=step_index,
                    action_taken=f"raised_{type(custom_exc).__name__}",
                    message=str(custom_exc),
                )
            )
            raise custom_exc

        server_exc = ChaosServerError(
            message=fault.message or f"Tool '{tool_name}' failed with simulated error.",
            status_code=fault.status_code,
        )
        self.history.append(
            FaultRecord(
                fault_type=fault.fault_type,
                tool=tool_name,
                step=step_index,
                action_taken="raised_ChaosServerError",
                message=str(server_exc),
            )
        )
        raise server_exc

    async def aevaluate_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],  # noqa: ARG002
        step_index: int,
    ) -> None:
        """Asynchronously evaluate and inject faults into async tool executions."""
        fault = self._find_matching_tool_fault(tool_name, step_index)
        if fault is None:
            return

        fault.increment_trigger()

        if fault.fault_type == FaultType.LATENCY:
            if fault.delay_ms > 0:
                await asyncio.sleep(fault.delay_ms / 1000.0)
            self.history.append(
                FaultRecord(
                    fault_type=fault.fault_type,
                    tool=tool_name,
                    step=step_index,
                    action_taken=f"delayed_{fault.delay_ms}ms",
                    message=fault.message,
                )
            )
            return

        if fault.fault_type == FaultType.TIMEOUT:
            if fault.duration_seconds > 0:
                await asyncio.sleep(fault.duration_seconds)
            timeout_exc = ChaosTimeoutError(
                message=fault.message or f"Tool '{tool_name}' timed out.",
                duration_seconds=fault.duration_seconds,
            )
            self.history.append(
                FaultRecord(
                    fault_type=fault.fault_type,
                    tool=tool_name,
                    step=step_index,
                    action_taken="raised_ChaosTimeoutError",
                    message=str(timeout_exc),
                )
            )
            raise timeout_exc

        if fault.custom_exception is not None:
            custom_exc: Exception = (
                fault.custom_exception()
                if isinstance(fault.custom_exception, type)
                else fault.custom_exception
            )
            self.history.append(
                FaultRecord(
                    fault_type=fault.fault_type,
                    tool=tool_name,
                    step=step_index,
                    action_taken=f"raised_{type(custom_exc).__name__}",
                    message=str(custom_exc),
                )
            )
            raise custom_exc

        server_exc = ChaosServerError(
            message=fault.message or f"Tool '{tool_name}' failed with simulated error.",
            status_code=fault.status_code,
        )
        self.history.append(
            FaultRecord(
                fault_type=fault.fault_type,
                tool=tool_name,
                step=step_index,
                action_taken="raised_ChaosServerError",
                message=str(server_exc),
            )
        )
        raise server_exc

    def _build_mutated_payload(self, fault: Fault) -> ResponsePayload:
        """Construct a synthetic ResponsePayload reflecting corrupted or safety outputs."""
        if fault.fault_type == FaultType.MALFORMED_JSON:
            return ResponsePayload(
                content=fault.corrupted_output or '{"status": "partial", "items": [',
                finish_reason="stop",
            )

        if fault.fault_type == FaultType.CONTENT_FILTER:
            return ResponsePayload(
                content=fault.refusal_text or "The request was refused by content safety policies.",
                finish_reason="content_filter",
            )

        if fault.fault_type == FaultType.HALLUCINATED_TOOL:
            call = ToolCallRecord(
                function_name=fault.hallucinated_tool_name or "undefined_action_executor",
                arguments=fault.hallucinated_arguments or {"cmd": "rm -rf /", "force": True},
            )
            return ResponsePayload(
                content=None,
                tool_calls=[call],
                finish_reason="tool_calls",
            )

        return ResponsePayload(content="Corrupted output", finish_reason="stop")

    def _synthesize_exception(self, fault: Fault, adapter: BaseProviderAdapter) -> Exception:
        """Construct either a native SDK exception or a clean ChaosError."""
        if fault.custom_exception is not None:
            return cast(
                Exception,
                fault.custom_exception()
                if isinstance(fault.custom_exception, type)
                else fault.custom_exception,
            )

        if fault.native:
            native_exc = build_native_provider_exception(fault, adapter)
            if native_exc is not None:
                return native_exc

        # Fallback to TraceReplay ChaosError hierarchy
        if fault.fault_type == FaultType.RATE_LIMIT:
            return ChaosRateLimitError(
                message=fault.message or "Rate limit exceeded (429 Too Many Requests)",
                retry_after=fault.retry_after,
            )

        if fault.fault_type == FaultType.TIMEOUT:
            return ChaosTimeoutError(
                message=fault.message or "Request timed out",
                duration_seconds=fault.duration_seconds,
            )

        if fault.fault_type == FaultType.SERVER_ERROR:
            return ChaosServerError(
                message=fault.message or f"Internal server error ({fault.status_code})",
                status_code=fault.status_code,
            )

        if fault.fault_type == FaultType.CONTEXT_LENGTH:
            return ChaosContextLengthError(
                message=fault.message or "This model's maximum context length exceeded.",
            )

        return ChaosServerError(message=fault.message or "Unknown chaos fault occurred.")
