"""Integration tests for Health and Root API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_endpoint() -> None:
    """Test the root '/' endpoint returns API metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "TraceReplay" in data["name"]
    assert data["docs"] == "/docs"
    assert data["api_v1"] == "/api/v1"


def test_health_endpoint() -> None:
    """Test the '/api/v1/health' endpoint returns database connectivity info."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ("healthy", "degraded")
    assert "database" in data
    assert "project" in data
    assert "version" in data
