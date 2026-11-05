# Context manager and session coordinator for TraceReplay test runs.

from __future__ import annotations

import contextvars
from typing import Any

from tracereplay.config import TraceReplayConfig, get_config
from tracereplay.core.recorder import Recorder
from tracereplay.core.replayer import Replayer
from tracereplay.matcher.rules import RequestMatcher
from tracereplay.models import ReplayMode
from tracereplay.sanitizer import Sanitizer
from tracereplay.storage.json_storage import JsonStorageEngine

_CURRENT_SESSION: contextvars.ContextVar[TraceReplaySession | None] = contextvars.ContextVar(
    "current_session", default=None
)


class TraceReplaySession:
    # Manages recording and replaying contexts across sync and async boundaries.

    def __init__(
        self,
        name: str,
        mode: ReplayMode | str | None = None,
        config: TraceReplayConfig | None = None,
        storage: JsonStorageEngine | None = None,
        sanitizer: Sanitizer | None = None,
        matcher: RequestMatcher | None = None,
    ) -> None:

        self.name = name
        self.config = config or get_config()
        self.mode = ReplayMode(mode) if mode is not None else self.config.mode
        self.storage = storage or JsonStorageEngine(config=self.config)
        self.sanitizer = sanitizer or Sanitizer(config=self.config)
        self.matcher = matcher or RequestMatcher(config=self.config)

        self.recorder: Recorder | None = None
        self.replayer: Replayer | None = None
        self._token: contextvars.Token[TraceReplaySession | None] | None = None

        # Resolve effective mode for AUTO
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

        if exc_type is None and self.recorder is not None and self.recorder.interactions:
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
) -> TraceReplaySession:
    # Convenience context manager to start a TraceReplay session
    return TraceReplaySession(name=name, mode=mode, config=config)
