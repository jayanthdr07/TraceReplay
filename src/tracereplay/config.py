"""Configuration manager for TraceReplay.

Supports settings via environment variables, code overrides, and defaults.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from tracereplay.exceptions import ConfigurationError
from tracereplay.models import ReplayMode


def _get_env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "on")


def _get_env_list(name: str, default: list[str]) -> list[str]:
    val = os.getenv(name)
    if not val:
        return default
    return [item.strip().lower() for item in val.split(",") if item.strip()]


class TraceReplayConfig(BaseModel):
    # Global configuration settings for TraceReplay.

    mode: ReplayMode = Field(default=ReplayMode.AUTO)
    fixtures_dir: Path = Field(default=Path(".tracereplay/fixtures"))
    redact_keys: list[str] = Field(
        default_factory=lambda: [
            "authorization",
            "api-key",
            "x-api-key",
            "openai-api-key",
            "anthropic-api-key",
            "gemini-api-key",
        ]
    )

    redact_patterns: list[str] = Field(default_factory=list)
    simulate_latency: bool = Field(default=False)
    match_parameters: bool = Field(default=True)
    ignored_parameters: list[str] = Field(
        default_factory=lambda: ["seed", "user", "request_id", "timestamp"]
    )
    strict_ordering: bool = Field(default=True)
    allow_streaming: bool = Field(default=True)
    max_fixture_size_mb: float = Field(default=50.0, ge=1.0)
    semantic_matching: bool = Field(default=False)
    semantic_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    semantic_action: str = Field(default="accept")

    @classmethod
    def from_env(cls) -> TraceReplayConfig:
        # Create a configuration instance populated from system environment variables.
        raw_mode = os.getenv("TRACEREPLAY_MODE", "auto").lower()
        try:
            mode = ReplayMode(raw_mode)
        except ValueError as err:
            valid_modes = [m.value for m in ReplayMode]
            raise ConfigurationError(
                f"Invalid TRACEREPLAY_MODE '{raw_mode}'. Valid modes: {valid_modes}"
            ) from err

        raw_fixtures_dir = os.getenv("TRACEREPLAY_DIR")
        fixtures_dir = Path(raw_fixtures_dir) if raw_fixtures_dir else Path(".tracereplay/fixtures")

        redact_keys = _get_env_list(
            "TRACEREPLAY_REDACT_KEYS",
            default=[
                "authorization",
                "api-key",
                "x-api-key",
                "openai-api-key",
                "anthropic-api-key",
                "gemini-api-key",
            ],
        )

        ignored_params = _get_env_list(
            "TRACEREPLAY_IGNORED_PARAMS",
            default=["seed", "user", "request_id", "timestamp"],
        )

        return cls(
            mode=mode,
            fixtures_dir=fixtures_dir,
            redact_keys=redact_keys,
            ignored_parameters=ignored_params,
            simulate_latency=_get_env_bool("TRACEREPLAY_SIMULATE_LATENCY", False),
            match_parameters=_get_env_bool("TRACEREPLAY_MATCH_PARAMETERS", True),
            strict_ordering=_get_env_bool("TRACEREPLAY_STRICT_ORDERING", True),
            allow_streaming=_get_env_bool("TRACEREPLAY_ALLOW_STREAMING", True),
            semantic_matching=_get_env_bool("TRACEREPLAY_SEMANTIC_MATCHING", False),
            semantic_threshold=float(os.getenv("TRACEREPLAY_SEMANTIC_THRESHOLD", "0.85")),
            semantic_action=os.getenv("TRACEREPLAY_SEMANTIC_ACTION", "accept").lower(),
        )


# Global singleton configuration instance
_GLOBAL_CONFIG: TraceReplayConfig | None = None


def get_config() -> TraceReplayConfig:
    """Retrieve the current active TraceReplay configuration."""
    global _GLOBAL_CONFIG
    if _GLOBAL_CONFIG is None:
        _GLOBAL_CONFIG = TraceReplayConfig.from_env()
    return _GLOBAL_CONFIG


def configure(**kwargs: Any) -> TraceReplayConfig:
    """Update global configuration parameters programmatically."""
    global _GLOBAL_CONFIG
    current = get_config().model_dump()
    current.update(kwargs)
    _GLOBAL_CONFIG = TraceReplayConfig(**current)
    return _GLOBAL_CONFIG


def reset_config() -> None:
    """Reset the global configuration to environment/default settings."""
    global _GLOBAL_CONFIG
    _GLOBAL_CONFIG = None
