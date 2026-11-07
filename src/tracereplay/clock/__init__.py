"""Deterministic clock and freeze-time engine for TraceReplay.

Controls simulated time, freezes system clocks to match fixture recording timestamps,
and speeds up test suites by eliminating real sleep delays.
"""

from __future__ import annotations

from tracereplay.clock.engine import DeterministicClock, freeze_time
from tracereplay.clock.models import ClockConfig, ClockState, parse_datetime_input

__all__ = [
    "ClockConfig",
    "ClockState",
    "DeterministicClock",
    "freeze_time",
    "parse_datetime_input",
]
