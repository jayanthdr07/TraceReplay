"""Unit tests for Supabase client initialization and health checks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.config import Settings
from app.db.client import (
    check_database_health,
    get_supabase_admin_client,
    get_supabase_client,
)


def test_client_local_mode(local_mode_settings: Settings) -> None:
    """In local mode, client returns None and health check reports filesystem status."""
    import app.db.client as client_module

    client_module._supabase_client = None
    client_module._supabase_admin_client = None

    with patch("app.db.client.get_settings", return_value=local_mode_settings):
        client = get_supabase_client()
        assert client is None

        health = check_database_health()
        assert health["mode"] == "local"
        assert health["status"] == "healthy"
        assert health["provider"] == "filesystem"


def test_client_cloud_mode(mock_settings: Settings) -> None:
    """In cloud mode with valid mock credentials, create_client is invoked."""
    mock_supabase_instance = MagicMock()
    select_mock = mock_supabase_instance.table.return_value.select.return_value
    select_mock.limit.return_value.execute.return_value.data = [
        {"id": "00000000-0000-0000-0000-000000000000"}
    ]

    with (
        patch("app.db.client.get_settings", return_value=mock_settings),
        patch("app.db.client.create_client", return_value=mock_supabase_instance),
    ):
        # Force re-creation
        import app.db.client as client_module

        client_module._supabase_client = None
        client_module._supabase_admin_client = None

        client = get_supabase_client()
        assert client is not None

        admin = get_supabase_admin_client()
        assert admin is not None

        health = check_database_health()
        assert health["mode"] == "cloud"
        assert health["status"] == "connected"
        assert health["query_success"] is True
