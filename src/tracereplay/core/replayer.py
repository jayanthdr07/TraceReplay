#  Replay engine for deterministic playback of recorded LLM fixtures.

from __future__ import annotations

import asyncio
import time
from typing import Any

from tracereplay.config import TraceReplayConfig, get_config
from tracereplay.exceptions import RequestMismatchError, ToolExecutionError
from tracereplay.matcher.rules import RequestMatcher
from tracereplay.models import RequestPayload, ResponsePayload, SessionRecord
from tracereplay.storage.json_storage import JsonStorageEngine


class Replayer:
    # Replays recorded LLM interactions from persistent fixtures with zero-live-fallback.

    def __init__(
        self,
        session_name: str,
        storage: JsonStorageEngine,
        matcher: RequestMatcher | None = None,
        config: TraceReplayConfig | None = None,
    ) -> None:
        self.session_name = session_name
        self.storage = storage
        self.config = config or get_config()
        self.matcher = matcher or RequestMatcher(config=self.config)
        self._current_index = 0
        self._current_tool_index = 0
        self._record: SessionRecord | None = None

    @property
    def record(self) -> SessionRecord:
        # Lazy-load and cache the recorded session fixture.
        if self._record is None:
            self._record = self.storage.load(self.session_name)
        return self._record

    def replay_interaction(self, request: RequestPayload) -> ResponsePayload:
        # Evaluate request against recorded fixture and return determination response.
        session = self.record
        matched, result = self.matcher.find_match(request, session, start_index=self._current_index)

        if not result.is_match or matched is None:
            diff_msg = result.diff or "\n".join(result.differences)
            summary = "; ".join(result.differences)
            raise RequestMismatchError(
                f"Request mismatch in session '{self.session_name}' at step "
                f"{self._current_index}: {summary}\n{diff_msg}",
                expected=result.expected,
                actual=result.actual,
                diff=result.diff,
                interaction_index=self._current_index,
            )

        if self.config.simulate_latency and matched.duration_ms > 0:
            time.sleep(matched.duration_ms / 1000.0)

        self._current_index = matched.index + 1
        return matched.response

    async def areplay_interaction(self, request: RequestPayload) -> ResponsePayload:
        # Async variant supporting simulated latency without blocking the event loop.
        session = self.record
        matched, result = self.matcher.find_match(request, session, start_index=self._current_index)

        if not result.is_match or matched is None:
            diff_msg = result.diff or "\n".join(result.differences)
            summary = "; ".join(result.differences)
            raise RequestMismatchError(
                f"Request mismatch in session '{self.session_name}' at step "
                f"{self._current_index}: {summary}\n{diff_msg}",
                expected=result.expected,
                actual=result.actual,
                diff=result.diff,
                interaction_index=self._current_index,
            )

        if self.config.simulate_latency and matched.duration_ms > 0:
            await asyncio.sleep(matched.duration_ms / 1000.0)

        self._current_index = matched.index + 1
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
        if expected_tool.error is not None:
            raise RuntimeError(expected_tool.error)
        return expected_tool.result
