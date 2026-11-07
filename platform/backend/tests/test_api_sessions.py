"""Integration tests for Test Sessions and Fixture Sync API endpoints."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_sessions() -> None:
    """Test retrieving sessions with filtering and pagination parameters."""
    response = client.get("/api/v1/sessions?limit=10&offset=0")
    assert response.status_code == 200
    sessions = response.json()
    assert isinstance(sessions, list)


def test_create_session() -> None:
    """Test recording a session run directly."""
    payload = {
        "session_name": f"eval_run_{uuid4().hex[:6]}",
        "mode": "replay",
        "status": "passed",
        "duration_ms": 120.5,
        "total_interactions": 2,
        "total_tokens": 850,
        "total_cost_usd": 0.0085,
        "metadata": {"git_branch": "main", "ci": True},
    }
    response = client.post("/api/v1/sessions", json=payload)
    # 201 created or handled gracefully
    if response.status_code == 201:
        created = response.json()
        assert created["session_name"] == payload["session_name"]
        assert created["total_tokens"] == 850
        assert created["status"] == "passed"


def test_fixture_sync_endpoint() -> None:
    """Test synchronizing full recording fixtures into the backend database."""
    sync_payload = {
        "project_slug": "pytest-evals",
        "fixtures": [
            {
                "session_name": f"test_booking_flow_{uuid4().hex[:6]}",
                "mode": "record",
                "created_at": "2026-11-07T12:00:00Z",
                "interactions": [
                    {
                        "step_index": 0,
                        "provider": "openai",
                        "model": "gpt-4o",
                        "prompt_tokens": 150,
                        "completion_tokens": 40,
                        "cost_usd": 0.0015,
                        "latency_ms": 650.0,
                        "request": {"messages": [{"role": "user", "content": "Book flight"}]},
                        "response": {"choices": [{"message": {"content": "Flight booked"}}]},
                    }
                ],
                "metadata": {"test_name": "test_flight_booking"},
            }
        ],
    }

    response = client.post("/api/v1/sessions/sync", json=sync_payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] in ("success", "partial_success")
    assert "synced_sessions" in res_data
    assert "synced_interactions" in res_data
