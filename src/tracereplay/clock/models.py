"""Data models and configuration schemas for deterministic clock and time freezing."""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def parse_datetime_input(
    target: datetime.datetime | datetime.date | str | float | int,
) -> datetime.datetime:
    """Parse various datetime representations into an aware UTC datetime object."""
    if isinstance(target, datetime.datetime):
        if target.tzinfo is None:
            return target.replace(tzinfo=datetime.timezone.utc)
        return target.astimezone(datetime.timezone.utc)

    if isinstance(target, datetime.date):
        return datetime.datetime(
            target.year, target.month, target.day, tzinfo=datetime.timezone.utc
        )

    if isinstance(target, (int, float)):
        return datetime.datetime.fromtimestamp(target, tz=datetime.timezone.utc)

    if isinstance(target, str):
        cleaned = target.strip().replace(" UTC", "+00:00").replace("Z", "+00:00")
        try:
            dt = datetime.datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.astimezone(datetime.timezone.utc)
        except ValueError as err:
            raise ValueError(
                f"Cannot parse datetime from string '{target}'. Expected ISO format."
            ) from err

    raise TypeError(f"Unsupported datetime input type: {type(target).__name__}")


class ClockState(BaseModel):
    """Runtime tracking of the deterministic simulated clock."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    initial_time: datetime.datetime
    current_time: datetime.datetime
    initial_monotonic: float = Field(default=0.0)
    total_advanced_seconds: float = Field(default=0.0, ge=0.0)
    sleep_calls: list[float] = Field(default_factory=list)

    @property
    def current_timestamp(self) -> float:
        """Return the current mock time as a POSIX float timestamp."""
        return self.current_time.timestamp()

    @property
    def current_monotonic(self) -> float:
        """Return the current mock monotonic clock reading."""
        return self.initial_monotonic + self.total_advanced_seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert clock state to a serializable dictionary."""
        return {
            "initial_time": self.initial_time.isoformat(),
            "current_time": self.current_time.isoformat(),
            "total_advanced_seconds": self.total_advanced_seconds,
            "sleep_calls_count": len(self.sleep_calls),
            "total_slept_seconds": sum(self.sleep_calls),
        }


class ClockConfig(BaseModel):
    """Configuration options for deterministic time control."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    target_time: datetime.datetime | datetime.date | str | float | int | None = None
    auto_freeze_to_fixture: bool = False
    tick_increment: float = Field(default=0.0, ge=0.0)
    simulate_sleep: bool = True
    ignore_modules: list[str] = Field(
        default_factory=lambda: ["threading", "asyncio", "tracereplay.clock"]
    )
