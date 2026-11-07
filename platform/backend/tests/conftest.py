"""Pytest fixtures and configuration for backend tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.config import Settings, get_settings

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[Settings, None, None]:
    """Provide isolated mock settings for testing."""
    monkeypatch.setenv("PROJECT_NAME", "TraceReplay Test Platform")
    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.setenv("SUPABASE_URL", "https://mock-test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "mock-anon-key-12345")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "mock-service-role-key-99999")
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:3000"]')

    get_settings.cache_clear()
    settings = get_settings()
    yield settings
    get_settings.cache_clear()


@pytest.fixture
def local_mode_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[Settings, None, None]:
    """Provide isolated local mode settings (no Supabase credentials)."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    get_settings.cache_clear()
    settings = Settings(
        supabase_url=None,
        supabase_key=None,
        supabase_service_role_key=None,
        database_url=None,
    )
    yield settings
    get_settings.cache_clear()
