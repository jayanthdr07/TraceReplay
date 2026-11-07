"""Data models, Pydantic schemas, and transfer objects for TraceReplay Platform."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RoleEnum(str, Enum):
    """Team member authorization roles."""

    OWNER = "owner"
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class SessionStatusEnum(str, Enum):
    """Test session execution status outcomes."""

    PASSED = "passed"
    FAILED = "failed"
    DRIFT_DETECTED = "drift_detected"


# Organization Schemas


class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=50)


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationRead(OrganizationBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None = None


# Team Member Schemas


class TeamMemberBase(BaseModel):
    user_id: UUID
    role: RoleEnum = RoleEnum.DEVELOPER


class TeamMemberCreate(TeamMemberBase):
    org_id: UUID


class TeamMemberRead(TeamMemberBase):
    id: UUID
    org_id: UUID
    created_at: datetime


# Project Schemas


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=50)
    description: str = ""


class ProjectCreate(ProjectBase):
    org_id: UUID


class ProjectRead(ProjectBase):
    id: UUID
    org_id: UUID
    api_key_hash: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


# Test Session Schemas


class TestSessionBase(BaseModel):
    __test__ = False

    session_name: str
    mode: str = "auto"
    status: SessionStatusEnum = SessionStatusEnum.PASSED
    duration_ms: float = 0.0
    total_interactions: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    fixture_storage_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TestSessionCreate(TestSessionBase):
    project_id: UUID | None = None


class TestSessionRead(TestSessionBase):
    id: UUID
    project_id: UUID | None = None
    created_at: datetime


class TestSessionFilter(BaseModel):
    project_id: UUID | None = None
    status: SessionStatusEnum | None = None
    mode: str | None = None
    search: str | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


# LLM Interaction Schemas


class InteractionBase(BaseModel):
    step_index: int = 0
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    request_payload: dict[str, Any] = Field(default_factory=dict)
    response_payload: dict[str, Any] = Field(default_factory=dict)


class InteractionCreate(InteractionBase):
    session_id: UUID


class InteractionRead(InteractionBase):
    id: UUID
    session_id: UUID
    created_at: datetime


# Tool Execution Schemas


class ToolExecutionBase(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    duration_ms: float = 0.0
    error: str | None = None


class ToolExecutionCreate(ToolExecutionBase):
    session_id: UUID


class ToolExecutionRead(ToolExecutionBase):
    id: UUID
    session_id: UUID
    created_at: datetime


# Analytics & Metrics Schemas


class ModelUsageStat(BaseModel):
    model: str
    provider: str
    total_calls: int
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: float


class LatencyDistributionStat(BaseModel):
    p50_ms: float
    p90_ms: float
    p99_ms: float
    avg_ms: float


class AnalyticsOverviewRead(BaseModel):
    total_sessions: int = 0
    total_interactions: int = 0
    total_replays: int = 0
    estimated_cost_saved_usd: float = 0.0
    total_tokens_recorded: int = 0
    replay_success_rate: float = 100.0
    average_latency_ms: float = 0.0
    top_models: list[ModelUsageStat] = Field(default_factory=list)
    latency_distribution: LatencyDistributionStat | None = None


# Fixture Sync Schemas


class FixtureSyncRequest(BaseModel):
    project_slug: str = "default-project"
    fixtures: list[dict[str, Any]] = Field(default_factory=list)


class FixtureSyncResponse(BaseModel):
    synced_sessions: int = 0
    synced_interactions: int = 0
    errors: list[str] = Field(default_factory=list)
    status: str = "success"
