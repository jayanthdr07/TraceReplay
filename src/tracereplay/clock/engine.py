"""Deterministic clock engine and time-freezing patcher for TraceReplay."""

from __future__ import annotations

import asyncio
import datetime
import functools
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

from tracereplay.clock.models import ClockConfig, ClockState, parse_datetime_input

_real_datetime = datetime.datetime
_real_date = datetime.date
_real_time = time.time
_real_monotonic = time.monotonic
_real_sleep = time.sleep

_ACTIVE_CLOCK: DeterministicClock | None = None


class MockDatetime(_real_datetime):
    """Subclass of datetime.datetime that redirects now() and utcnow() to DeterministicClock."""

    @classmethod
    def now(cls, tz: datetime.tzinfo | None = None) -> datetime.datetime:  # type: ignore[override]
        if _ACTIVE_CLOCK is not None:
            return _ACTIVE_CLOCK.now(tz=tz)
        return _real_datetime.now(tz=tz)

    @classmethod
    def utcnow(cls) -> datetime.datetime:  # type: ignore[override]
        if _ACTIVE_CLOCK is not None:
            return _ACTIVE_CLOCK.utcnow()
        return _real_datetime.utcnow()


class MockDate(_real_date):
    """Subclass of datetime.date that redirects today() to DeterministicClock."""

    @classmethod
    def today(cls) -> datetime.date:  # type: ignore[override]
        if _ACTIVE_CLOCK is not None:
            return _ACTIVE_CLOCK.today()
        return _real_date.today()


class DeterministicClock:
    """Controls simulated time, freezes the system clock, and speeds up sleep delays."""

    def __init__(
        self,
        target_time: datetime.datetime | datetime.date | str | float | int | None = None,
        config: ClockConfig | None = None,
    ) -> None:
        self.config = config or ClockConfig()
        raw_target = target_time if target_time is not None else self.config.target_time
        if raw_target is not None:
            parsed = parse_datetime_input(raw_target)
        else:
            parsed = _real_datetime.now(datetime.timezone.utc)

        self.state = ClockState(
            initial_time=parsed,
            current_time=parsed,
            initial_monotonic=_real_monotonic(),
        )
        self._lock = threading.RLock()
        self._is_patched: bool = False
        self._patched_targets: list[tuple[Any, str, Any]] = []

    def now(self, tz: datetime.tzinfo | None = None) -> datetime.datetime:
        """Return current simulated time as an aware or naive datetime."""
        with self._lock:
            cur = self.state.current_time
            if self.config.tick_increment > 0:
                self.advance(seconds=self.config.tick_increment)

            if tz is None:
                # Return local naive datetime matching real datetime.now() behavior
                return cur.astimezone().replace(tzinfo=None)
            return cur.astimezone(tz)

    def utcnow(self) -> datetime.datetime:
        """Return current simulated time as a naive UTC datetime."""
        with self._lock:
            cur = self.state.current_time
            if self.config.tick_increment > 0:
                self.advance(seconds=self.config.tick_increment)
            return cur.replace(tzinfo=None)

    def today(self) -> datetime.date:
        """Return current simulated date."""
        return self.now().date()

    def time(self) -> float:
        """Return current simulated POSIX timestamp."""
        with self._lock:
            ts = self.state.current_timestamp
            if self.config.tick_increment > 0:
                self.advance(seconds=self.config.tick_increment)
            return ts

    def monotonic(self) -> float:
        """Return current simulated monotonic clock reading."""
        with self._lock:
            mono = self.state.current_monotonic
            if self.config.tick_increment > 0:
                self.advance(seconds=self.config.tick_increment)
            return mono

    def sleep(self, seconds: float) -> None:
        """Simulate time.sleep by advancing the clock instantly without real blocking."""
        with self._lock:
            if self.config.simulate_sleep:
                self.state.sleep_calls.append(seconds)
                self.advance(seconds=seconds)
            else:
                _real_sleep(seconds)

    def advance(
        self,
        seconds: float | int = 0,
        delta: datetime.timedelta | None = None,
    ) -> datetime.datetime:
        """Advance the simulated clock by seconds or a timedelta."""
        with self._lock:
            dt_delta = delta if delta is not None else datetime.timedelta(seconds=seconds)
            self.state.current_time += dt_delta
            self.state.total_advanced_seconds += dt_delta.total_seconds()
            return self.state.current_time

    def tick(
        self,
        seconds: float | int = 1,
        delta: datetime.timedelta | None = None,
    ) -> datetime.datetime:
        """Advance the clock by seconds (default 1s)."""
        return self.advance(seconds=seconds, delta=delta)

    def set_time(
        self,
        target_time: datetime.datetime | datetime.date | str | float | int,
    ) -> datetime.datetime:
        """Set the simulated clock to an exact target time."""
        with self._lock:
            parsed = parse_datetime_input(target_time)
            diff = (parsed - self.state.initial_time).total_seconds()
            self.state.current_time = parsed
            self.state.total_advanced_seconds = max(0.0, diff)
            return parsed

    def patch(self) -> DeterministicClock:
        """Activate the deterministic clock by patching datetime and time modules."""
        global _ACTIVE_CLOCK
        if self._is_patched:
            return self

        _ACTIVE_CLOCK = self
        self._patched_targets = []

        # 1. Patch core datetime module
        dt_mod = sys.modules.get("datetime")
        if dt_mod is not None:
            self._patched_targets.append((dt_mod, "datetime", getattr(dt_mod, "datetime", None)))
            self._patched_targets.append((dt_mod, "date", getattr(dt_mod, "date", None)))
            setattr(dt_mod, "datetime", MockDatetime)  # noqa: B010
            setattr(dt_mod, "date", MockDate)  # noqa: B010

        # 2. Patch core time module
        time_mod = sys.modules.get("time")
        if time_mod is not None:
            self._patched_targets.append((time_mod, "time", getattr(time_mod, "time", None)))
            self._patched_targets.append(
                (time_mod, "monotonic", getattr(time_mod, "monotonic", None))
            )
            self._patched_targets.append((time_mod, "sleep", getattr(time_mod, "sleep", None)))
            setattr(time_mod, "time", self.time)  # noqa: B010
            setattr(time_mod, "monotonic", self.monotonic)  # noqa: B010
            setattr(time_mod, "sleep", self.sleep)  # noqa: B010

        # 3. Patch already imported modules that did `from datetime import datetime`
        ignored = set(self.config.ignore_modules) | {"sys", "builtins", "typing"}
        for mod_name, mod in list(sys.modules.items()):
            if not mod or mod_name in ignored:
                continue
            if any(mod_name.startswith(f"{ig}.") for ig in ignored):
                continue
            try:
                if getattr(mod, "datetime", None) is _real_datetime:
                    self._patched_targets.append((mod, "datetime", _real_datetime))
                    setattr(mod, "datetime", MockDatetime)  # noqa: B010
                if getattr(mod, "date", None) is _real_date:
                    self._patched_targets.append((mod, "date", _real_date))
                    setattr(mod, "date", MockDate)  # noqa: B010
                if getattr(mod, "time", None) is _real_time:
                    self._patched_targets.append((mod, "time", _real_time))
                    setattr(mod, "time", self.time)  # noqa: B010
            except Exception:
                pass

        self._is_patched = True
        return self

    def unpatch(self) -> None:
        """Deactivate the clock and restore all original datetime and time functions."""
        global _ACTIVE_CLOCK
        if not self._is_patched:
            return

        for obj, attr_name, original_val in reversed(self._patched_targets):
            try:
                if original_val is not None:
                    setattr(obj, attr_name, original_val)
                else:
                    delattr(obj, attr_name)
            except Exception:
                pass

        self._patched_targets.clear()
        _ACTIVE_CLOCK = None
        self._is_patched = False

    def __enter__(self) -> DeterministicClock:
        return self.patch()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.unpatch()

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Support decorator usage across synchronous and asynchronous functions."""
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with self:
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                with self:
                    return func(*args, **kwargs)

            return sync_wrapper


def freeze_time(
    target_time: datetime.datetime | datetime.date | str | float | int | None = None,
    tick_increment: float = 0.0,
    simulate_sleep: bool = True,
) -> DeterministicClock:
    """Convenience factory creating a DeterministicClock context manager / decorator."""
    cfg = ClockConfig(
        target_time=target_time if isinstance(target_time, (datetime.datetime, str)) else None,
        tick_increment=tick_increment,
        simulate_sleep=simulate_sleep,
    )
    return DeterministicClock(target_time=target_time, config=cfg)
