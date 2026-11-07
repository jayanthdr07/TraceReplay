"""Unit tests for backend Pydantic schemas and models."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.db.models import (
    AnalyticsOverviewRead,
    InteractionCreate,
    ModelUsageStat,
    OrganizationCreate,
    OrganizationRead,
    ProjectCreate,
    ProjectRead,
    SessionStatusEnum,
    TestSessionCreate,
    TestSessionRead,
    ToolExecutionCreate,
)


def test_organization_models() -> None:
    """Test OrganizationCreate and OrganizationRead serialization."""
    org_in = OrganizationCreate(name="Acme AI Corp", slug="acme-ai")
    assert org_in.name == "Acme AI Corp"
    assert org_in.slug == "acme-ai"

    org_id = uuid4()
    now = datetime.now(timezone.utc)
    org_read = OrganizationRead(id=org_id, name="Acme AI Corp", slug="acme-ai", created_at=now)
    assert org_read.id == org_id
    assert org_read.name == "Acme AI Corp"


def test_project_models() -> None:
    """Test ProjectCreate and ProjectRead schemas."""
    org_id = uuid4()
    proj_in = ProjectCreate(org_id=org_id, name="Support Agent", slug="support-agent")
    assert proj_in.org_id == org_id
    assert proj_in.slug == "support-agent"

    proj_id = uuid4()
    now = datetime.now(timezone.utc)
    proj_read = ProjectRead(
        id=proj_id,
        org_id=org_id,
        name="Support Agent",
        slug="support-agent",
        created_at=now,
    )
    assert proj_read.id == proj_id


def test_test_session_models() -> None:
    """Test TestSession creation, status validation, and metrics."""
    proj_id = uuid4()
    session_in = TestSessionCreate(
        project_id=proj_id,
        session_name="eval_flow_v1",
        mode="replay",
        status=SessionStatusEnum.PASSED,
        duration_ms=45.2,
        total_interactions=3,
        total_tokens=1500,
        total_cost_usd=0.015,
    )
    assert session_in.total_tokens == 1500
    assert session_in.status == SessionStatusEnum.PASSED

    session_id = uuid4()
    now = datetime.now(timezone.utc)
    session_read = TestSessionRead(
        id=session_id,
        project_id=proj_id,
        session_name="eval_flow_v1",
        mode="replay",
        status=SessionStatusEnum.PASSED,
        duration_ms=45.2,
        total_interactions=3,
        total_tokens=1500,
        total_cost_usd=0.015,
        created_at=now,
    )
    assert session_read.id == session_id


def test_interaction_models() -> None:
    """Test Interaction payload serialization."""
    session_id = uuid4()
    interaction_in = InteractionCreate(
        session_id=session_id,
        step_index=0,
        provider="openai",
        model="gpt-4o",
        prompt_tokens=120,
        completion_tokens=45,
        cost_usd=0.0012,
        latency_ms=850.5,
        request_payload={"messages": [{"role": "user", "content": "Hi"}]},
        response_payload={"choices": [{"message": {"content": "Hello!"}}]},
    )
    assert interaction_in.model == "gpt-4o"
    assert interaction_in.prompt_tokens == 120


def test_tool_execution_models() -> None:
    """Test ToolExecution arguments and output serialization."""
    session_id = uuid4()
    tool_in = ToolExecutionCreate(
        session_id=session_id,
        tool_name="search_database",
        arguments={"query": "capital of France"},
        result={"city": "Paris"},
        duration_ms=12.4,
    )
    assert tool_in.tool_name == "search_database"
    assert tool_in.result == {"city": "Paris"}


def test_analytics_overview_model() -> None:
    """Test AnalyticsOverview aggregation payload."""
    stat = ModelUsageStat(
        model="gpt-4o",
        provider="openai",
        total_calls=150,
        total_tokens=45000,
        total_cost_usd=0.45,
        avg_latency_ms=620.0,
    )
    overview = AnalyticsOverviewRead(
        total_sessions=15,
        total_interactions=150,
        total_replays=120,
        estimated_cost_saved_usd=1.35,
        total_tokens_recorded=45000,
        replay_success_rate=99.2,
        average_latency_ms=580.0,
        top_models=[stat],
    )
    assert overview.total_sessions == 15
    assert len(overview.top_models) == 1
    assert overview.top_models[0].model == "gpt-4o"
