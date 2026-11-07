"""Supabase and database client connectivity for TraceReplay Platform."""

from __future__ import annotations

import logging
from typing import Any

from supabase import Client, create_client

from ..config import get_settings

logger = logging.getLogger(__name__)

_supabase_client: Client | None = None
_supabase_admin_client: Client | None = None


def get_supabase_client() -> Client | None:
    """Return an authenticated client instance for Supabase, or None in local mode."""
    global _supabase_client
    settings = get_settings()

    if settings.is_local_mode:
        return None

    if _supabase_client is None and settings.supabase_url and settings.supabase_key:
        try:
            _supabase_client = create_client(settings.supabase_url, settings.supabase_key)
            logger.info("Supabase client initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            return None

    return _supabase_client


def get_supabase_admin_client() -> Client | None:
    """Return an admin (service_role) client instance for administrative operations."""
    global _supabase_admin_client
    settings = get_settings()

    if settings.is_local_mode or not settings.supabase_service_role_key:
        return get_supabase_client()

    if _supabase_admin_client is None and settings.supabase_url:
        try:
            _supabase_admin_client = create_client(
                settings.supabase_url, settings.supabase_service_role_key
            )
            logger.info("Supabase admin client initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase admin client: {e}")
            return None

    return _supabase_admin_client


def check_database_health() -> dict[str, Any]:
    """Inspect and report database connectivity status."""
    settings = get_settings()

    if settings.is_local_mode:
        fixtures_path = settings.get_resolved_fixtures_dir()
        fixture_count = len(list(fixtures_path.glob("*.json"))) if fixtures_path.exists() else 0
        return {
            "mode": "local",
            "status": "healthy",
            "provider": "filesystem",
            "fixtures_dir": str(fixtures_path),
            "fixtures_found": fixture_count,
        }

    client = get_supabase_client()
    if client is None:
        return {
            "mode": "cloud",
            "status": "unhealthy",
            "error": "Supabase client not initialized",
        }

    try:
        # Ping the organizations table to verify credentials and connectivity
        response = client.table("organizations").select("id").limit(1).execute()
        return {
            "mode": "cloud",
            "status": "connected",
            "provider": "supabase_postgresql",
            "url": settings.supabase_url,
            "query_success": True,
            "rows_returned": len(response.data) if hasattr(response, "data") else 0,
        }
    except Exception as e:
        return {
            "mode": "cloud",
            "status": "degraded",
            "provider": "supabase_postgresql",
            "error": str(e),
            "url": settings.supabase_url,
        }


def extract_records(data: Any) -> list[dict[str, Any]]:
    """Safely extract list of dictionary records from Supabase query data."""
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []
