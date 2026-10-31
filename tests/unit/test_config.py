"""Unit tests for TraceReplay configuration engine."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tracereplay.config import (
    TraceReplayConfig,
    configure,
    get_config,
    reset_config,
)
from tracereplay.exceptions import ConfigurationError
from tracereplay.models import ReplayMode


@pytest.fixture(autouse=True)
def _reset_global_config() -> Iterator[None]:
    """Ensure clean global configuration state before and after each test."""
    reset_config()
    yield
    reset_config()


def test_default_config_values() -> None:
    """Verify initial default configuration settings."""
    cfg = get_config()
    assert cfg.mode == ReplayMode.AUTO
    assert cfg.fixtures_dir == Path(".tracereplay/fixtures")
    assert "authorization" in cfg.redact_keys
    assert "api-key" in cfg.redact_keys
    assert "seed" in cfg.ignored_parameters
    assert cfg.simulate_latency is False
    assert cfg.match_parameters is True
    assert cfg.strict_ordering is True
    assert cfg.allow_streaming is True


def test_programmatic_configure() -> None:
    """Verify configure() updates global settings."""
    configure(
        mode=ReplayMode.RECORD,
        fixtures_dir=Path("tests/custom_fixtures"),
        simulate_latency=True,
    )
    cfg = get_config()
    assert cfg.mode == ReplayMode.RECORD
    assert cfg.fixtures_dir == Path("tests/custom_fixtures")
    assert cfg.simulate_latency is True


def test_config_from_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify reading configuration from environment variables."""
    monkeypatch.setenv("TRACEREPLAY_MODE", "replay")
    monkeypatch.setenv("TRACEREPLAY_DIR", "my_fixtures/llm")
    monkeypatch.setenv("TRACEREPLAY_SIMULATE_LATENCY", "true")
    monkeypatch.setenv("TRACEREPLAY_REDACT_KEYS", "api_key,secret_token")
    monkeypatch.setenv("TRACEREPLAY_IGNORED_PARAMS", "seed,custom_uuid")

    cfg = TraceReplayConfig.from_env()
    assert cfg.mode == ReplayMode.REPLAY
    assert cfg.fixtures_dir == Path("my_fixtures/llm")
    assert cfg.simulate_latency is True
    assert cfg.redact_keys == ["api_key", "secret_token"]
    assert cfg.ignored_parameters == ["seed", "custom_uuid"]


def test_invalid_env_mode_raises_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that an invalid TRACEREPLAY_MODE environment variable raises ConfigurationError."""
    monkeypatch.setenv("TRACEREPLAY_MODE", "super_magic_mode")
    with pytest.raises(ConfigurationError, match="Invalid TRACEREPLAY_MODE"):
        TraceReplayConfig.from_env()
