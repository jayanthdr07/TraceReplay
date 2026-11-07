"""Unit tests for backend configuration and settings."""

from __future__ import annotations

from app.config import Settings, get_settings


def test_settings_defaults(local_mode_settings: Settings) -> None:
    """Test default values when no environment variables are provided."""
    assert "TraceReplay" in local_mode_settings.project_name
    assert local_mode_settings.version == "0.1.0"
    assert local_mode_settings.is_local_mode is True


def test_cors_origins_parsing() -> None:
    """Test parsing of CORS origins from lists, comma strings, and JSON arrays."""
    # List of strings
    s1 = Settings(cors_origins=["http://localhost:3000", "http://example.com"])
    assert s1.cors_origins == ["http://localhost:3000", "http://example.com"]

    # Comma-separated string
    s2 = Settings(cors_origins="http://localhost:3000, https://app.tracereplay.io")
    assert "http://localhost:3000" in s2.cors_origins
    assert "https://app.tracereplay.io" in s2.cors_origins

    # JSON formatted string
    s3 = Settings(cors_origins='["http://localhost:3000", "http://localhost:8000"]')
    assert s3.cors_origins == ["http://localhost:3000", "http://localhost:8000"]


def test_is_local_mode_logic() -> None:
    """Test local mode detection based on URL and key presence."""
    # Missing credentials -> local mode True
    s_empty = Settings(supabase_url=None, supabase_key=None)
    assert s_empty.is_local_mode is True

    # Placeholder URL -> local mode True
    s_placeholder = Settings(
        supabase_url="https://your-project-id.supabase.co",
        supabase_key="eyJhbGciOi...",
    )
    assert s_placeholder.is_local_mode is True

    # Real URL and key -> local mode False
    s_real = Settings(
        supabase_url="https://oupcmmlldivrpbntydsy.supabase.co",
        supabase_key="sb_publishable_5FNiBa4yRa383qBFp0arPA_JaOdk6zt",
    )
    assert s_real.is_local_mode is False


def test_get_settings_cached_singleton() -> None:
    """Verify that get_settings caches the Settings instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
