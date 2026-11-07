"""System health and connectivity check endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from ...config import get_settings
from ...db.client import check_database_health

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", status_code=status.HTTP_200_OK)
def get_health() -> dict[str, Any]:
    """Inspect and return overall platform health and database connectivity."""
    settings = get_settings()
    db_health = check_database_health()
    overall_status = (
        "healthy" if db_health.get("status") in ("connected", "healthy") else "degraded"
    )

    return {
        "status": overall_status,
        "project": settings.project_name,
        "version": settings.version,
        "environment": settings.environment,
        "database": db_health,
    }
