"""Unit tests for the JSON storage engine and fixture resolver."""

from __future__ import annotations

from pathlib import Path

import pytest

from tracereplay.exceptions import FixtureNotFoundError, InvalidFixtureError
from tracereplay.models import (
    Interaction,
    OperationType,
    RequestPayload,
    ResponsePayload,
    SessionRecord,
    TokenUsage,
)
from tracereplay.storage.json_storage import JsonStorageEngine
from tracereplay.storage.resolver import FixtureResolver, sanitize_filename


def test_sanitize_filename() -> None:
    """Verify filename cleaning and unsafe character replacement."""
    assert sanitize_filename("test/checkout:order*") == "test_checkout_order"
    assert sanitize_filename("..safe_name..") == "safe_name"
    assert sanitize_filename("") == "default_fixture"


def test_fixture_resolver_safe_paths(tmp_path: Path) -> None:
    """Verify resolver constructs predictable paths within base directory."""
    resolver = FixtureResolver(base_dir=tmp_path)
    path = resolver.resolve("test_chat_session")
    assert path == tmp_path / "test_chat_session.json"
    assert not resolver.exists("test_chat_session")


def test_fixture_resolver_prevents_path_traversal(tmp_path: Path) -> None:
    """Verify that path traversal attempts raise ConfigurationError."""
    resolver = FixtureResolver(base_dir=tmp_path)
    # Even if someone tries directory traversal, sanitize_filename strips it or resolver catches it
    resolved = resolver.resolve("../../outside_dir")
    assert resolved.is_relative_to(tmp_path)


def test_atomic_save_and_load(tmp_path: Path) -> None:
    """Verify that a session is saved atomically and loaded back identically."""
    resolver = FixtureResolver(base_dir=tmp_path)
    storage = JsonStorageEngine(resolver=resolver)

    req = RequestPayload(
        provider="gemini",
        model="gemini-1.5-pro",
        operation=OperationType.CHAT_COMPLETION,
        prompt="Explain quantum physics",
    )
    res = ResponsePayload(
        content="Quantum physics is...",
        usage=TokenUsage(prompt_tokens=4, completion_tokens=10, total_tokens=14),
    )
    interaction = Interaction(
        session_id="sess_atom_1",
        index=0,
        duration_ms=210.5,
        request=req,
        response=res,
    )
    session = SessionRecord(name="test_quantum_session", interactions=[interaction])

    # 1. Save session
    saved_path = storage.save(session)
    assert saved_path.is_file()
    assert resolver.exists("test_quantum_session")

    # Ensure no leftover temporary files in directory
    temp_files = list(tmp_path.glob(".tmp_*"))
    assert len(temp_files) == 0

    # 2. Load session back
    loaded = storage.load("test_quantum_session")
    assert loaded.session_id == session.session_id
    assert loaded.name == "test_quantum_session"
    assert loaded.interactions[0].request.prompt == "Explain quantum physics"
    assert loaded.interactions[0].response.content == "Quantum physics is..."
    assert loaded.interactions[0].duration_ms == 210.5


def test_load_nonexistent_fixture_raises_error(tmp_path: Path) -> None:
    """Verify that loading a missing fixture raises FixtureNotFoundError."""
    resolver = FixtureResolver(base_dir=tmp_path)
    storage = JsonStorageEngine(resolver=resolver)
    with pytest.raises(FixtureNotFoundError, match="Fixture file not found"):
        storage.load("ghost_session_that_does_not_exist")


def test_load_malformed_json_raises_invalid_fixture_error(tmp_path: Path) -> None:
    """Verify that corrupt JSON raises InvalidFixtureError."""
    bad_file = tmp_path / "corrupted.json"
    bad_file.write_text("{ this is not valid JSON !!!", encoding="utf-8")

    storage = JsonStorageEngine(resolver=FixtureResolver(base_dir=tmp_path))
    with pytest.raises(InvalidFixtureError, match="Malformed JSON in fixture file"):
        storage.load(bad_file)


def test_load_schema_mismatch_raises_invalid_fixture_error(tmp_path: Path) -> None:
    """Verify that valid JSON with invalid schema raises InvalidFixtureError."""
    invalid_schema_file = tmp_path / "bad_schema.json"
    invalid_schema_file.write_text(
        '{"name": 12345, "interactions": "not_a_list"}', encoding="utf-8"
    )

    storage = JsonStorageEngine(resolver=FixtureResolver(base_dir=tmp_path))
    with pytest.raises(InvalidFixtureError, match="Schema validation failed"):
        storage.load(invalid_schema_file)
