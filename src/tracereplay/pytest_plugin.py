"""Pytest plugin integration for TraceReplay.

Provides pytest hooks, CLI options, markers, and fixtures for effortless
record/replay testing of LLM applications.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import pytest

from tracereplay.config import TraceReplayConfig, get_config
from tracereplay.core.session import TraceReplaySession
from tracereplay.models import ReplayMode
from tracereplay.providers.patcher import patch, unpatch
from tracereplay.storage.resolver import sanitize_filename


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register TraceReplay command-line options and ini settings with pytest."""
    group = parser.getgroup("tracereplay", "TraceReplay LLM recording and deterministic replay")

    group.addoption(
        "--tracereplay-mode",
        action="store",
        dest="tracereplay_mode",
        choices=["record", "replay", "auto", "passthrough"],
        default=None,
        help="TraceReplay execution mode (record, replay, auto, passthrough).",
    )
    group.addoption(
        "--tracereplay-dir",
        action="store",
        dest="tracereplay_dir",
        default=None,
        help="Custom root directory path for TraceReplay JSON fixture files.",
    )
    group.addoption(
        "--tracereplay-disable",
        action="store_true",
        dest="tracereplay_disable",
        default=False,
        help="Disable TraceReplay recording and replaying completely (run in passthrough).",
    )

    parser.addini(
        "tracereplay_mode",
        help="Default TraceReplay execution mode (record, replay, auto, passthrough).",
        default=None,
    )
    parser.addini(
        "tracereplay_dir",
        help="Default directory path for storing TraceReplay fixtures.",
        default=None,
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register the custom trace_replay marker with pytest."""
    config.addinivalue_line(
        "markers",
        "trace_replay(fixture=None, mode=None, dir=None, fork_at_step=None, fork_at_tool=None, "
        "fork_at_total_step=None, fork_session_name=None, fork_to_mode=None, chaos=None, "
        "guardrails=None, max_cost_usd=None, max_tokens=None, max_latency_ms=None): "
        "Record, replay, time-travel fork, inject AI faults, or enforce token/cost guardrails.",
    )


def generate_fixture_name(request: pytest.FixtureRequest) -> str:
    """Generate a clean, filesystem-safe fixture name from a pytest test request."""
    marker = request.node.get_closest_marker("trace_replay")
    param_suffix = ""
    callspec = getattr(request.node, "callspec", None)
    if callspec is not None and getattr(callspec, "id", None):
        param_suffix = f"_{callspec.id}"

    if marker:
        if "fixture" in marker.kwargs and marker.kwargs["fixture"]:
            base = str(marker.kwargs["fixture"])
            return sanitize_filename(f"{base}{param_suffix}")
        if marker.args and isinstance(marker.args[0], str) and marker.args[0]:
            base = marker.args[0]
            return sanitize_filename(f"{base}{param_suffix}")

    # Standard derivation: {module_stem}_{node_name}
    module_name = request.node.module.__name__ if hasattr(request.node, "module") else "test"
    short_module = module_name.split(".")[-1]
    node_name = request.node.name
    full_name = f"{short_module}_{node_name}"
    return sanitize_filename(full_name)


def resolve_tracereplay_config(request: pytest.FixtureRequest) -> TraceReplayConfig:
    """Resolve effective TraceReplayConfig based on CLI, INI, and environment settings."""
    base_config = get_config()
    cli_mode = request.config.getoption("tracereplay_mode")
    ini_mode = request.config.getini("tracereplay_mode")
    cli_dir = request.config.getoption("tracereplay_dir")
    ini_dir = request.config.getini("tracereplay_dir")

    updates: dict[str, Any] = {}

    effective_mode_str = cli_mode or ini_mode
    if effective_mode_str:
        updates["mode"] = ReplayMode(str(effective_mode_str).lower())

    effective_dir_str = cli_dir or ini_dir
    if effective_dir_str:
        updates["fixtures_dir"] = Path(str(effective_dir_str))

    if updates:
        return base_config.model_copy(update=updates)
    return base_config


def create_tracereplay_session(
    request: pytest.FixtureRequest,
    config: TraceReplayConfig,
) -> Generator[TraceReplaySession, None, None]:
    """Create and manage an active TraceReplaySession for a test execution."""
    if request.config.getoption("tracereplay_disable", default=False):
        sess = TraceReplaySession(
            name="disabled",
            mode=ReplayMode.PASSTHROUGH,
            config=config,
        )
        with sess:
            yield sess
        return

    marker = request.node.get_closest_marker("trace_replay")
    fixture_name = generate_fixture_name(request)

    target_dir = config.fixtures_dir
    if marker and "dir" in marker.kwargs and marker.kwargs["dir"]:
        target_dir = Path(str(marker.kwargs["dir"]))

    mode = config.mode
    if marker and "mode" in marker.kwargs and marker.kwargs["mode"]:
        mode = ReplayMode(str(marker.kwargs["mode"]).lower())

    session_config = config.model_copy(update={"fixtures_dir": target_dir, "mode": mode})

    fork_at_step = marker.kwargs.get("fork_at_step") if marker else None
    fork_at_tool = marker.kwargs.get("fork_at_tool") if marker else None
    fork_at_total_step = marker.kwargs.get("fork_at_total_step") if marker else None
    fork_session_name = marker.kwargs.get("fork_session_name") if marker else None
    raw_fork_to_mode = (
        marker.kwargs.get("fork_to_mode", ReplayMode.RECORD) if marker else ReplayMode.RECORD
    )
    fork_to_mode = ReplayMode(raw_fork_to_mode) if raw_fork_to_mode else ReplayMode.RECORD
    chaos_param = marker.kwargs.get("chaos") if marker else None
    guardrails_param = marker.kwargs.get("guardrails") if marker else None
    max_cost_usd_param = marker.kwargs.get("max_cost_usd") if marker else None
    max_tokens_param = marker.kwargs.get("max_tokens") if marker else None
    max_latency_ms_param = marker.kwargs.get("max_latency_ms") if marker else None

    sess = TraceReplaySession(
        name=fixture_name,
        mode=mode,
        config=session_config,
        fork_at_step=fork_at_step,
        fork_at_tool=fork_at_tool,
        fork_at_total_step=fork_at_total_step,
        fork_session_name=fork_session_name,
        fork_to_mode=fork_to_mode,
        chaos=chaos_param,
        guardrails=guardrails_param,
        max_cost_usd=max_cost_usd_param,
        max_tokens=max_tokens_param,
        max_latency_ms=max_latency_ms_param,
    )

    with sess:
        yield sess


def create_tracereplay_patch(
    session: TraceReplaySession,  # noqa: ARG001
) -> Generator[Callable[..., Any], None, None]:
    """Wrap AI clients with TraceReplay interceptors and auto-unpatch on teardown."""
    patched_clients: list[Any] = []

    def _patch_client(client: Any, provider: str | None = None) -> Any:
        patched = patch(client, provider=provider)
        patched_clients.append(patched)
        return patched

    yield _patch_client

    for client in patched_clients:
        unpatch(client)


@pytest.fixture
def tracereplay_config(request: pytest.FixtureRequest) -> TraceReplayConfig:
    """Resolve the effective TraceReplayConfig based on CLI, INI, and environment settings."""
    return resolve_tracereplay_config(request)


@pytest.fixture
def tracereplay_session(
    request: pytest.FixtureRequest,
    tracereplay_config: TraceReplayConfig,
) -> Generator[TraceReplaySession, None, None]:
    """Provide an active TraceReplaySession scoped to the executing test function."""
    yield from create_tracereplay_session(request, tracereplay_config)


@pytest.fixture
def tracereplay_patch(
    tracereplay_session: TraceReplaySession,
) -> Generator[Callable[..., Any], None, None]:
    """Wrap AI clients with TraceReplay interceptors and auto-unpatch on teardown."""
    yield from create_tracereplay_patch(tracereplay_session)


@pytest.fixture
def auto_patch(
    tracereplay_patch: Callable[..., Any],
) -> Callable[..., Any]:
    """Ergonomic alias for tracereplay_patch."""
    return tracereplay_patch


@pytest.fixture(autouse=True)
def _tracereplay_marker(
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    """Automatically activate TraceReplaySession for tests decorated
    with @pytest.mark.trace_replay.
    """
    marker = request.node.get_closest_marker("trace_replay")
    if marker is None:
        yield
        return

    # Trigger session fixture execution
    request.getfixturevalue("tracereplay_session")
    yield
