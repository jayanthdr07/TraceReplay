"""Tests for TraceReplay pytest plugin integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from tracereplay.config import TraceReplayConfig
from tracereplay.core.session import TraceReplaySession, get_current_session
from tracereplay.models import (
    Interaction,
    ReplayMode,
    RequestPayload,
    ResponsePayload,
    SessionRecord,
)
from tracereplay.pytest_plugin import (
    create_tracereplay_patch,
    create_tracereplay_session,
    generate_fixture_name,
    pytest_addoption,
    pytest_configure,
    resolve_tracereplay_config,
)
from tracereplay.storage.json_storage import JsonStorageEngine


class DummyOptionGroup:
    def __init__(self) -> None:
        self.options: list[tuple[Any, dict[str, Any]]] = []

    def addoption(self, *args: Any, **kwargs: Any) -> None:
        self.options.append((args, kwargs))


class DummyParser:
    def __init__(self) -> None:
        self.group = DummyOptionGroup()
        self.inis: list[tuple[str, dict[str, Any]]] = []

    def getgroup(self, name: str, description: str = "") -> DummyOptionGroup:
        return self.group

    def addini(self, name: str, help: str, default: Any = None) -> None:
        self.inis.append((name, {"help": help, "default": default}))


class DummyConfig:
    def __init__(self) -> None:
        self.inivalues: list[tuple[str, str]] = []

    def addinivalue_line(self, name: str, value: str) -> None:
        self.inivalues.append((name, value))


def test_pytest_addoption() -> None:
    parser = DummyParser()
    pytest_addoption(parser)  # type: ignore[arg-type]

    opt_names = [opt[0][0] for opt in parser.group.options]
    assert "--tracereplay-mode" in opt_names
    assert "--tracereplay-dir" in opt_names
    assert "--tracereplay-disable" in opt_names

    ini_names = [ini[0] for ini in parser.inis]
    assert "tracereplay_mode" in ini_names
    assert "tracereplay_dir" in ini_names


def test_pytest_configure_registers_marker() -> None:
    config = DummyConfig()
    pytest_configure(config)  # type: ignore[arg-type]

    assert len(config.inivalues) == 1
    assert config.inivalues[0][0] == "markers"
    assert "trace_replay" in config.inivalues[0][1]


def test_generate_fixture_name_default() -> None:
    req = MagicMock(spec=pytest.FixtureRequest)
    req.node.get_closest_marker.return_value = None
    req.node.module.__name__ = "tests.test_agent"
    req.node.name = "test_customer_chat"
    del req.node.callspec

    name = generate_fixture_name(req)
    assert name == "test_agent_test_customer_chat"


def test_generate_fixture_name_with_marker_kwargs() -> None:
    req = MagicMock(spec=pytest.FixtureRequest)
    marker = MagicMock()
    marker.kwargs = {"fixture": "custom_greeting_flow"}
    marker.args = ()
    req.node.get_closest_marker.return_value = marker
    del req.node.callspec

    name = generate_fixture_name(req)
    assert name == "custom_greeting_flow"


def test_generate_fixture_name_with_marker_args() -> None:
    req = MagicMock(spec=pytest.FixtureRequest)
    marker = MagicMock()
    empty_kwargs: dict[str, Any] = {}
    marker.kwargs = empty_kwargs
    marker.args = ("positional_flow_name",)
    req.node.get_closest_marker.return_value = marker
    del req.node.callspec

    name = generate_fixture_name(req)
    assert name == "positional_flow_name"


def test_generate_fixture_name_parameterized() -> None:
    req = MagicMock(spec=pytest.FixtureRequest)
    marker = MagicMock()
    marker.kwargs = {"fixture": "model_test"}
    marker.args = ()
    req.node.get_closest_marker.return_value = marker
    req.node.callspec = MagicMock()
    req.node.callspec.id = "gpt-4o"

    name = generate_fixture_name(req)
    assert name == "model_test_gpt-4o"


def test_resolve_tracereplay_config() -> None:
    req = MagicMock(spec=pytest.FixtureRequest)

    def mock_getoption(key: str) -> Any:
        options = {
            "tracereplay_mode": "record",
            "tracereplay_dir": "custom/fixtures",
        }
        return options.get(key)

    req.config.getoption.side_effect = mock_getoption
    req.config.getini.return_value = None

    cfg = resolve_tracereplay_config(req)
    assert cfg.mode == ReplayMode.RECORD
    assert cfg.fixtures_dir == Path("custom/fixtures")


def test_create_tracereplay_session_lifecycle(tmp_path: Path) -> None:
    cfg = TraceReplayConfig(fixtures_dir=tmp_path, mode=ReplayMode.RECORD)
    req = MagicMock(spec=pytest.FixtureRequest)
    req.config.getoption.return_value = False
    req.node.get_closest_marker.return_value = None
    req.node.module.__name__ = "test_mod"
    req.node.name = "test_session_run"
    del req.node.callspec

    session_gen = create_tracereplay_session(req, cfg)
    sess = next(session_gen)

    assert sess is not None
    assert sess.name == "test_mod_test_session_run"
    assert sess.mode == ReplayMode.RECORD
    assert sess.recorder is not None
    assert get_current_session() == sess

    sess.recorder.record_interaction(
        RequestPayload(provider="openai", model="gpt-4o", prompt="Hello"),
        ResponsePayload(content="World"),
    )

    with pytest.raises(StopIteration):
        next(session_gen)

    assert get_current_session() is None
    saved_file = tmp_path / "test_mod_test_session_run.json"
    assert saved_file.is_file()


def test_create_tracereplay_session_exception_does_not_flush(tmp_path: Path) -> None:
    cfg = TraceReplayConfig(fixtures_dir=tmp_path, mode=ReplayMode.RECORD)
    req = MagicMock(spec=pytest.FixtureRequest)
    req.config.getoption.return_value = False
    req.node.get_closest_marker.return_value = None
    req.node.module.__name__ = "test_mod"
    req.node.name = "test_failing_run"
    del req.node.callspec

    session_gen = create_tracereplay_session(req, cfg)
    sess = next(session_gen)

    assert sess is not None
    assert sess.recorder is not None
    sess.recorder.record_interaction(
        RequestPayload(provider="openai", model="gpt-4o", prompt="Failing interaction"),
        ResponsePayload(content="Err"),
    )

    # Simulate an uncaught exception in test
    with pytest.raises(RuntimeError, match="Test failure"):
        session_gen.throw(RuntimeError("Test failure"))

    saved_file = tmp_path / "test_mod_test_failing_run.json"
    assert not saved_file.exists()


def test_create_tracereplay_patch_auto_unpatch() -> None:
    class MockCompletions:
        def create(self, **kwargs: Any) -> str:
            return "original"

    class MockChat:
        def __init__(self) -> None:
            self.completions = MockCompletions()

    class MockClient:
        def __init__(self) -> None:
            self.chat = MockChat()

    client = MockClient()
    mock_session = MagicMock()
    patch_gen = create_tracereplay_patch(mock_session)
    patch_fn = next(patch_gen)

    patched_client = patch_fn(client)
    assert hasattr(patched_client, "unpatch")
    assert patched_client.chat.completions.create != MockCompletions.create

    with pytest.raises(StopIteration):
        next(patch_gen)

    # After teardown, original method is restored
    assert patched_client.chat.completions.create.__name__ == "create"


def test_auto_mode_switch_record_to_replay(tmp_path: Path) -> None:
    cfg = TraceReplayConfig(fixtures_dir=tmp_path, mode=ReplayMode.AUTO)
    storage = JsonStorageEngine(config=cfg)

    # 1. First run: fixture does not exist -> RECORD mode
    req1 = MagicMock()
    req1.config.getoption.return_value = False
    req1.node.get_closest_marker.return_value = None
    req1.node.module.__name__ = "tests.unit"
    req1.node.name = "test_auto_switch"
    del req1.node.callspec

    sess1 = create_tracereplay_session(req1, cfg)
    s1 = next(sess1)
    assert s1 is not None
    assert s1.mode == ReplayMode.RECORD
    assert s1.recorder is not None

    # Pre-save fixture so it exists for session 2
    session_record = SessionRecord(
        name="unit_test_auto_switch",
        interactions=[
            Interaction(
                session_id="unit_test_auto_switch",
                index=0,
                request=RequestPayload(provider="openai", model="gpt-4o", prompt="Hi"),
                response=ResponsePayload(content="Hi back!"),
            )
        ],
    )
    storage.save(session_record)

    with pytest.raises(StopIteration):
        next(sess1)

    # 2. Second run: fixture exists -> REPLAY mode
    req2 = MagicMock()
    req2.config.getoption.return_value = False
    req2.node.get_closest_marker.return_value = None
    req2.node.module.__name__ = "tests.unit"
    req2.node.name = "test_auto_switch"
    del req2.node.callspec

    sess2 = create_tracereplay_session(req2, cfg)
    s2 = next(sess2)
    assert s2 is not None
    assert s2.mode == ReplayMode.REPLAY
    assert s2.replayer is not None

    with pytest.raises(StopIteration):
        next(sess2)


def test_tracereplay_disable_forces_passthrough(tmp_path: Path) -> None:
    cfg = TraceReplayConfig(fixtures_dir=tmp_path, mode=ReplayMode.RECORD)
    req = MagicMock(spec=pytest.FixtureRequest)

    def mock_disable_option(key: str, default: Any = None) -> Any:
        return True if key == "tracereplay_disable" else default

    req.config.getoption.side_effect = mock_disable_option
    req.node.get_closest_marker.return_value = None

    session_gen = create_tracereplay_session(req, cfg)
    sess = next(session_gen)

    assert sess is not None
    assert sess.mode == ReplayMode.PASSTHROUGH
    assert sess.recorder is None
    assert sess.replayer is None

    with pytest.raises(StopIteration):
        next(session_gen)


# ============================================================================
# Real Pytest Integration Tests (Using Fixtures Injected by pytest)
# ============================================================================


@pytest.mark.trace_replay(fixture="test_real_plugin_fixture")
def test_real_plugin_injection(
    tracereplay_session: TraceReplaySession,
    auto_patch: Any,
) -> None:
    """Verify that Pytest automatically injects tracereplay_session and auto_patch."""
    assert tracereplay_session.name == "test_real_plugin_fixture"
    assert get_current_session() is tracereplay_session
    assert callable(auto_patch)
    if tracereplay_session.recorder:
        tracereplay_session.recorder.record_interaction(
            RequestPayload(provider="openai", model="gpt-4o", prompt="ping"),
            ResponsePayload(content="pong"),
        )


@pytest.mark.trace_replay(fixture="test_e2e_patched_flow")
def test_end_to_end_plugin_with_patched_client(
    tracereplay_session: TraceReplaySession,
    tracereplay_patch: Any,
) -> None:
    """Full end-to-end test proving client interception and session recording work together."""
    class FakeMsg:
        content: str = "AI response: Order #123 is shipped."

    class FakeChoice:
        message: FakeMsg = FakeMsg()

    class FakeResponse:
        choices: list[Any] = [FakeChoice()]
        usage: Any = None

    class FakeCompletions:
        def create(self, **kwargs: Any) -> Any:
            return FakeResponse()

    class FakeChat:
        completions: FakeCompletions = FakeCompletions()

    class FakeOpenAI:
        chat: FakeChat = FakeChat()

    client = tracereplay_patch(FakeOpenAI(), provider="openai")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Where is my order?"}],
    )
    assert response.choices[0].message.content == "AI response: Order #123 is shipped."
    if tracereplay_session.recorder:
        assert len(tracereplay_session.recorder.interactions) >= 1

