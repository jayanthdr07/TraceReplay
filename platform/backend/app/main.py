"""TraceReplay Platform Backend API - Main FastAPI Entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import analytics, health, interactions, projects, sessions
from .config import get_settings


def create_app() -> FastAPI:
    """Initialize and configure the FastAPI application."""
    settings = get_settings()

    fastapi_app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        description=(
            "Unified enterprise dashboard backend for recording, analyzing, "
            "and mocking multi-turn LLM agent sessions."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Attach CORS middleware for frontend dashboard access
    origins = (
        settings.cors_origins
        if isinstance(settings.cors_origins, list)
        else ["http://localhost:3000"]
    )
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API v1 Routers
    api_prefix = settings.api_v1_prefix
    fastapi_app.include_router(health.router, prefix=api_prefix)
    fastapi_app.include_router(projects.router, prefix=api_prefix)
    fastapi_app.include_router(sessions.router, prefix=api_prefix)
    fastapi_app.include_router(interactions.router, prefix=api_prefix)
    fastapi_app.include_router(analytics.router, prefix=api_prefix)

    @fastapi_app.get("/", tags=["Root"])
    def root() -> dict[str, str]:
        """Root status ping with link to API documentation."""
        return {
            "name": settings.project_name,
            "version": settings.version,
            "status": "online",
            "docs": "/docs",
            "api_v1": api_prefix,
        }

    return fastapi_app


app = create_app()
