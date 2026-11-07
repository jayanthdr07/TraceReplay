#  Replay engine for deterministic playback of recorded LLM fixtures.

from __future__ import annotations

import asyncio
import json
import time
import warnings
from typing import Any

from tracereplay.config import TraceReplayConfig, get_config
from tracereplay.exceptions import (
    RequestMismatchError,
    SemanticDriftError,
    ToolExecutionError,
)
from tracereplay.matcher.rules import RequestMatcher
from tracereplay.models import (
    Interaction,
    RequestPayload,
    ResponsePayload,
    SessionRecord,
    ToolCallRecord,
)
from tracereplay.semantic import (
    DriftAction,
    DriftReport,
    SemanticConfig,
    SemanticMatcher,
    calculate_semantic_similarity,
)
from tracereplay.storage.json_storage import JsonStorageEngine


class Replayer:
    # Replays recorded LLM interactions from persistent fixtures with zero-live-fallback.

    def __init__(
        self,
        session_name: str,
        storage: JsonStorageEngine,
        matcher: RequestMatcher | None = None,
        config: TraceReplayConfig | None = None,
        semantic_matcher: SemanticMatcher | None = None,
    ) -> None:
        self.session_name = session_name
        self.storage = storage
        self.config = config or get_config()
        self.matcher = matcher or RequestMatcher(config=self.config)

        if semantic_matcher is not None:
            self.semantic_matcher: SemanticMatcher | None = semantic_matcher
        elif self.config.semantic_matching:
            action = DriftAction(self.config.semantic_action)
            self.semantic_matcher = SemanticMatcher(
                config=SemanticConfig(
                    enabled=True,
                    threshold=self.config.semantic_threshold,
                    action=action,
                ),
                global_config=self.config,
            )
        else:
            self.semantic_matcher = None

        self._current_index = 0
        self._current_tool_index = 0
        self._record: SessionRecord | None = None
        self.replayed_interactions: list[Interaction] = []
        self.replayed_tool_executions: list[ToolCallRecord] = []

    @property
    def drift_report(self) -> DriftReport:
        """Return the cumulative prompt drift report."""
        if self.semantic_matcher is not None:
            return self.semantic_matcher.report
        return DriftReport()

    @property
    def record(self) -> SessionRecord:
        # Lazy-load and cache the recorded session fixture.
        if self._record is None:
            self._record = self.storage.load(self.session_name)
        return self._record

    def _resolve_interaction(self, request: RequestPayload) -> Interaction:
        """Resolve incoming request against fixture using exact or semantic matching."""
        session = self.record
        matched, result = self.matcher.find_match(request, session, start_index=self._current_index)

        if result.is_match and matched is not None:
            if self.semantic_matcher is not None:
                exact_record = self.semantic_matcher.compare_semantic(
                    matched.request,
                    request,
                    step_index=self._current_index,
                    matched_index=matched.index,
                )
                self.semantic_matcher.report.records.append(exact_record)
            return matched

        # Exact match failed. Check if semantic matching is active
        if self.semantic_matcher is not None and self.semantic_matcher.config.enabled:
            sem_matched, drift_record = self.semantic_matcher.find_match(
                request, session, start_index=self._current_index
            )

            if drift_record.is_match and sem_matched is not None:
                if self.semantic_matcher.config.action == DriftAction.WARN:
                    warnings.warn(
                        f"[TraceReplay Drift] Prompt drift detected at step "
                        f"{self._current_index} ({drift_record.similarity_score:.1%} similarity, "
                        f"threshold {drift_record.threshold:.1%}):\n{drift_record.diff}",
                        UserWarning,
                        stacklevel=2,
                    )
                return sem_matched

            # Drift exceeded threshold or structural mismatch
            diff_msg = drift_record.diff or "\n".join(drift_record.differences)
            summary = (
                f"Prompt drift exceeded at step {self._current_index}: "
                f"similarity {drift_record.similarity_score:.2%} < threshold "
                f"{drift_record.threshold:.2%}"
            )
            raise SemanticDriftError(
                f"Semantic drift exceeded in session '{self.session_name}' at step "
                f"{self._current_index}: {summary}\n{diff_msg}",
                similarity_score=drift_record.similarity_score,
                threshold=drift_record.threshold,
                expected={"text": drift_record.expected_text},
                actual={"text": drift_record.actual_text},
                diff=drift_record.diff,
                semantic_diff=drift_record.diff,
                inline_diff=drift_record.inline_diff,
                interaction_index=self._current_index,
            )

        # Semantic matching is disabled: standard RequestMismatchError with intelligent hint
        diff_msg = result.diff or "\n".join(result.differences)
        summary = "; ".join(result.differences)

        hint = ""
        if self._current_index < len(session.interactions):
            candidate_req = session.interactions[self._current_index].request
            exp_text = candidate_req.prompt or (
                json.dumps(candidate_req.messages) if candidate_req.messages else ""
            )
            act_text = request.prompt or (json.dumps(request.messages) if request.messages else "")
            if exp_text and act_text:
                sim = calculate_semantic_similarity(exp_text, act_text)
                if sim >= 0.70:
                    hint = (
                        f"\n[Hint] Prompts are {sim:.1%} similar. Enable "
                        f"semantic matching (`semantic_matching=True, "
                        f"semantic_threshold={max(0.5, round(sim - 0.05, 2))}`) "
                        "to allow this prompt drift."
                    )

        raise RequestMismatchError(
            f"Request mismatch in session '{self.session_name}' at step "
            f"{self._current_index}: {summary}\n{diff_msg}{hint}",
            expected=result.expected,
            actual=result.actual,
            diff=result.diff,
            interaction_index=self._current_index,
        )

    def replay_interaction(self, request: RequestPayload) -> ResponsePayload:
        # Evaluate request against recorded fixture and return determination response.
        matched = self._resolve_interaction(request)

        if self.config.simulate_latency and matched.duration_ms > 0:
            time.sleep(matched.duration_ms / 1000.0)

        self._current_index = matched.index + 1
        self.replayed_interactions.append(matched)
        return matched.response

    async def areplay_interaction(self, request: RequestPayload) -> ResponsePayload:
        # Async variant supporting simulated latency without blocking the event loop.
        matched = self._resolve_interaction(request)

        if self.config.simulate_latency and matched.duration_ms > 0:
            await asyncio.sleep(matched.duration_ms / 1000.0)

        self._current_index = matched.index + 1
        self.replayed_interactions.append(matched)
        return matched.response

    def replay_tool_execution(self, function_name: str, arguments: dict[str, Any]) -> Any:
        # Replay a recorded tool function execution with sequential verification.
        session = self.record
        if self._current_tool_index >= len(session.tool_executions):
            raise ToolExecutionError(
                f"No more recorded tool executions in session '{self.session_name}'. "
                f"Attempted to execute '{function_name}' at tool index {self._current_tool_index}.",
                details={
                    "function_name": function_name,
                    "arguments": arguments,
                    "tool_index": self._current_tool_index,
                    "total_recorded": len(session.tool_executions),
                },
            )

        expected_tool = session.tool_executions[self._current_tool_index]
        if expected_tool.function_name != function_name:
            raise ToolExecutionError(
                f"Tool name mismatch at index {self._current_tool_index}: "
                f"expected '{expected_tool.function_name}', received '{function_name}'.",
                details={
                    "expected_function": expected_tool.function_name,
                    "actual_function": function_name,
                    "tool_index": self._current_tool_index,
                },
            )

        if expected_tool.arguments != arguments:
            raise ToolExecutionError(
                f"Tool argument mismatch for '{function_name}' at "
                f"index {self._current_tool_index}: "
                f"expected {expected_tool.arguments}, received {arguments}.",
                details={
                    "function_name": function_name,
                    "expected_arguments": expected_tool.arguments,
                    "actual_arguments": arguments,
                    "tool_index": self._current_tool_index,
                },
            )

        if self.config.simulate_latency and expected_tool.duration_ms > 0:
            time.sleep(expected_tool.duration_ms / 1000.0)

        self._current_tool_index += 1
        self.replayed_tool_executions.append(expected_tool)
        if expected_tool.error is not None:
            raise RuntimeError(expected_tool.error)
        return expected_tool.result

    async def areplay_tool_execution(self, function_name: str, arguments: dict[str, Any]) -> Any:
        # Async replay of a recorded tool function execution with sequential verification.
        session = self.record
        if self._current_tool_index >= len(session.tool_executions):
            raise ToolExecutionError(
                f"No more recorded tool executions in session '{self.session_name}'. "
                f"Attempted to execute '{function_name}' at tool index {self._current_tool_index}.",
                details={
                    "function_name": function_name,
                    "arguments": arguments,
                    "tool_index": self._current_tool_index,
                    "total_recorded": len(session.tool_executions),
                },
            )

        expected_tool = session.tool_executions[self._current_tool_index]
        if expected_tool.function_name != function_name:
            raise ToolExecutionError(
                f"Tool name mismatch at index {self._current_tool_index}: "
                f"expected '{expected_tool.function_name}', received '{function_name}'.",
                details={
                    "expected_function": expected_tool.function_name,
                    "actual_function": function_name,
                    "tool_index": self._current_tool_index,
                },
            )

        if expected_tool.arguments != arguments:
            raise ToolExecutionError(
                f"Tool argument mismatch for '{function_name}' at "
                f"index {self._current_tool_index}: "
                f"expected {expected_tool.arguments}, received {arguments}.",
                details={
                    "function_name": function_name,
                    "expected_arguments": expected_tool.arguments,
                    "actual_arguments": arguments,
                    "tool_index": self._current_tool_index,
                },
            )

        if self.config.simulate_latency and expected_tool.duration_ms > 0:
            await asyncio.sleep(expected_tool.duration_ms / 1000.0)

        self._current_tool_index += 1
        self.replayed_tool_executions.append(expected_tool)
        if expected_tool.error is not None:
            raise RuntimeError(expected_tool.error)
        return expected_tool.result
