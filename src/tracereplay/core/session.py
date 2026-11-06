# Context manager and session coordinator for TraceReplay test runs.

from __future__ import annotations

import contextvars
from collections.abc import Callable
from typing import Any

from tracereplay.chaos.engine import ChaosEngine
from tracereplay.chaos.models import ChaosConfig, Fault
from tracereplay.config import TraceReplayConfig, get_config
from tracereplay.core.recorder import Recorder
from tracereplay.core.replayer import Replayer
from tracereplay.exceptions import (
    FixtureNotFoundError,
    LiveFallbackProhibitedError,
    TraceReplayError,
)
from tracereplay.matcher.rules import RequestMatcher
from tracereplay.models import Interaction, ReplayMode, ToolCallRecord
from tracereplay.sanitizer import Sanitizer
from tracereplay.storage.json_storage import JsonStorageEngine

_CURRENT_SESSION: contextvars.ContextVar[TraceReplaySession | None] = contextvars.ContextVar(
    "current_session", default=None
)


class TraceReplaySession:
    # Manages recording, replaying, and time-travel forking across sync and async boundaries.

    def __init__(
        self,
        name: str,
        mode: ReplayMode | str | None = None,
        config: TraceReplayConfig | None = None,
        storage: JsonStorageEngine | None = None,
        sanitizer: Sanitizer | None = None,
        matcher: RequestMatcher | None = None,
        fork_at_step: int | None = None,
        fork_at_tool: str | Callable[..., Any] | None = None,
        fork_at_total_step: int | None = None,
        fork_session_name: str | None = None,
        fork_to_mode: ReplayMode | str = ReplayMode.RECORD,
        chaos: ChaosConfig | list[Fault] | None = None,
    ) -> None:
        self.name = name
        self.config = config or get_config()
        self.mode = ReplayMode(mode) if mode is not None else self.config.mode
        self.storage = storage or JsonStorageEngine(config=self.config)
        self.sanitizer = sanitizer or Sanitizer(config=self.config)
        self.matcher = matcher or RequestMatcher(config=self.config)

        # Time-travel forking parameters
        self.fork_at_step = fork_at_step
        if fork_at_tool is None or isinstance(fork_at_tool, str):
            self.fork_at_tool: str | None = fork_at_tool
        else:
            self.fork_at_tool = getattr(fork_at_tool, "__name__", str(fork_at_tool))
        self.fork_at_total_step = fork_at_total_step
        self.fork_session_name = fork_session_name
        self.fork_to_mode = ReplayMode(fork_to_mode)

        # AI Chaos Engineering
        self.chaos_config: ChaosConfig | None = None
        self.chaos_engine: ChaosEngine | None = None
        if chaos is not None:
            if isinstance(chaos, ChaosConfig):
                self.chaos_config = chaos
            elif isinstance(chaos, list):
                self.chaos_config = ChaosConfig(faults=chaos)
            else:
                self.chaos_config = ChaosConfig()
            self.chaos_engine = ChaosEngine(self.chaos_config)

        self._is_forked: bool = False
        self._llm_step_count: int = 0
        self._tool_step_count: int = 0
        self._total_step_count: int = 0

        self.recorder: Recorder | None = None
        self.replayer: Replayer | None = None
        self._token: contextvars.Token[TraceReplaySession | None] | None = None

        # Resolve effective mode
        if self.is_forking_configured:
            if not self.storage.resolver.exists(self.name):
                raise FixtureNotFoundError(
                    f"Cannot fork session '{self.name}': base fixture does not exist at "
                    f"'{self.storage.resolver.resolve(self.name)}'."
                )
            effective_mode = ReplayMode.REPLAY
        else:
            effective_mode = self.mode
            if effective_mode == ReplayMode.AUTO:
                if self.storage.resolver.exists(self.name):
                    effective_mode = ReplayMode.REPLAY
                else:
                    effective_mode = ReplayMode.RECORD

        self.mode = effective_mode

        if self.mode == ReplayMode.RECORD:
            self.recorder = Recorder(
                session_name=self.name,
                storage=self.storage,
                sanitizer=self.sanitizer,
                config=self.config,
            )
        elif self.mode == ReplayMode.REPLAY:
            self.replayer = Replayer(
                session_name=self.name,
                storage=self.storage,
                matcher=self.matcher,
                config=self.config,
            )

    @property
    def is_forking_configured(self) -> bool:
        """Return True if this session is configured with time-travel fork triggers."""
        return (
            self.fork_at_step is not None
            or self.fork_at_tool is not None
            or self.fork_at_total_step is not None
        )

    @property
    def is_forked(self) -> bool:
        """Return True if this session has executed its fork transition."""
        return self._is_forked

    def check_fork_trigger(self, tool_name: str | None = None) -> bool:
        """Evaluate if the current LLM step or tool call satisfies a fork trigger condition."""
        if not self.is_forking_configured or self._is_forked:
            return False

        should_fork = False

        # 1. Tool-based fork trigger
        if (
            tool_name is not None
            and self.fork_at_tool is not None
            and tool_name == self.fork_at_tool
        ):
            should_fork = True

        # 2. LLM step-based fork trigger
        if (
            tool_name is None
            and self.fork_at_step is not None
            and self._llm_step_count >= self.fork_at_step
        ):
            should_fork = True

        # 3. Total step-based fork trigger
        if (
            self.fork_at_total_step is not None
            and self._total_step_count >= self.fork_at_total_step
        ):
            should_fork = True

        if should_fork:
            self._execute_fork()
            return True

        return False

    def fork(
        self,
        session_name: str | None = None,
        mode: ReplayMode | str = ReplayMode.RECORD,
    ) -> None:
        """Manually trigger a time-travel fork at the current execution point."""
        if self._is_forked:
            raise TraceReplayError(
                f"Session '{self.name}' has already been forked to '{self.mode.value}' mode."
            )
        if session_name:
            self.fork_session_name = session_name
        self.fork_to_mode = ReplayMode(mode)
        self._execute_fork()

    def _execute_fork(self) -> None:
        """Execute the transition from REPLAY to the target fork mode (RECORD or PASSTHROUGH)."""
        self._is_forked = True
        new_mode = self.fork_to_mode
        target_name = self.fork_session_name or f"{self.name}_fork"

        if new_mode == ReplayMode.RECORD:
            pre_interactions: list[Interaction] = []
            pre_tools: list[ToolCallRecord] = []

            if self.replayer is not None:
                pre_interactions = [i.model_copy() for i in self.replayer.replayed_interactions]
                pre_tools = [t.model_copy() for t in self.replayer.replayed_tool_executions]

            self.recorder = Recorder(
                session_name=target_name,
                storage=self.storage,
                sanitizer=self.sanitizer,
                config=self.config,
            )
            self.recorder.interactions = [
                i.model_copy(update={"session_id": self.recorder.session_id})
                for i in pre_interactions
            ]
            self.recorder.tool_executions = pre_tools
            self.recorder._interaction_count = len(self.recorder.interactions)

        self.name = target_name
        self.mode = new_mode

    def notify_llm_call_completed(self) -> None:
        """Register completion of an LLM interaction step."""
        self._llm_step_count += 1
        self._total_step_count += 1

    def notify_tool_call_completed(self) -> None:
        """Register completion of a local tool call step."""
        self._tool_step_count += 1
        self._total_step_count += 1

    def record_tool_call(self, tool_call: ToolCallRecord) -> None:
        """Record a tool function invocation."""
        if self.recorder is not None:
            self.recorder.record_tool_execution(tool_call)

    def replay_tool_call(self, function_name: str, arguments: dict[str, Any]) -> Any:
        """Replay a recorded tool function invocation."""
        if self.replayer is None:
            raise LiveFallbackProhibitedError(
                f"Cannot replay tool call '{function_name}': session is not in REPLAY mode."
            )
        return self.replayer.replay_tool_execution(function_name, arguments)

    async def areplay_tool_call(self, function_name: str, arguments: dict[str, Any]) -> Any:
        """Async replay of a recorded tool function invocation."""
        if self.replayer is None:
            raise LiveFallbackProhibitedError(
                f"Cannot replay tool call '{function_name}': session is not in REPLAY mode."
            )
        return await self.replayer.areplay_tool_execution(function_name, arguments)

    def __enter__(self) -> TraceReplaySession:
        self._token = _CURRENT_SESSION.set(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if self._token is not None:
            _CURRENT_SESSION.reset(self._token)
            self._token = None

        if (
            exc_type is None
            and self.recorder is not None
            and (self.recorder.interactions or self.recorder.tool_executions)
        ):
            self.recorder.flush()

    async def __aenter__(self) -> TraceReplaySession:
        return self.__enter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)


def get_current_session() -> TraceReplaySession | None:
    return _CURRENT_SESSION.get()


def session(
    name: str,
    mode: ReplayMode | str | None = None,
    config: TraceReplayConfig | None = None,
    storage: JsonStorageEngine | None = None,
    sanitizer: Sanitizer | None = None,
    matcher: RequestMatcher | None = None,
    fork_at_step: int | None = None,
    fork_at_tool: str | Callable[..., Any] | None = None,
    fork_at_total_step: int | None = None,
    fork_session_name: str | None = None,
    fork_to_mode: ReplayMode | str = ReplayMode.RECORD,
    chaos: ChaosConfig | list[Fault] | None = None,
) -> TraceReplaySession:
    """Convenience context manager to start a TraceReplay session."""
    return TraceReplaySession(
        name=name,
        mode=mode,
        config=config,
        storage=storage,
        sanitizer=sanitizer,
        matcher=matcher,
        fork_at_step=fork_at_step,
        fork_at_tool=fork_at_tool,
        fork_at_total_step=fork_at_total_step,
        fork_session_name=fork_session_name,
        fork_to_mode=fork_to_mode,
        chaos=chaos,
    )
