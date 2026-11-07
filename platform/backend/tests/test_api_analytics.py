"""Integration tests for Analytics Overview API endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_analytics_overview_endpoint() -> None:
    """Test retrieving aggregated metrics for the dashboard."""
    response = client.get("/api/v1/analytics/overview")
    assert response.status_code == 200
    overview = response.json()

    assert "total_sessions" in overview
    assert "total_interactions" in overview
    assert "total_replays" in overview
    assert "estimated_cost_saved_usd" in overview
    assert "total_tokens_recorded" in overview
    assert "replay_success_rate" in overview
    assert "average_latency_ms" in overview
    assert "top_models" in overview
    assert isinstance(overview["top_models"], list)
    assert overview["replay_success_rate"] >= 0.0
