"""Test sessions management and fixture synchronization API endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, status

from ...config import get_settings
from ...db.client import extract_records, get_supabase_admin_client, get_supabase_client
from ...db.models import (
    FixtureSyncRequest,
    FixtureSyncResponse,
    SessionStatusEnum,
    TestSessionCreate,
    TestSessionRead,
)

router = APIRouter(prefix="/sessions", tags=["Sessions"])


def _load_local_sessions(fixtures_dir: Path) -> list[TestSessionRead]:
    """Parse real fixture JSON files from local disk into TestSessionRead models."""
    sessions: list[TestSessionRead] = []
    if not fixtures_dir.exists():
        return sessions

    for fixture_file in fixtures_dir.glob("*.json"):
        try:
            with open(fixture_file, encoding="utf-8") as f:
                data = json.load(f)

            created_raw = data.get("created_at")
            if created_raw:
                try:
                    dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                except ValueError:
                    dt = datetime.now(timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            session_id_raw = data.get("session_id")
            try:
                sid = UUID(session_id_raw) if session_id_raw else uuid4()
            except ValueError:
                sid = uuid4()

            interactions = data.get("interactions", [])
            total_tokens = sum(
                (item.get("prompt_tokens", 0) + item.get("completion_tokens", 0))
                for item in interactions
            )
            total_cost = sum(item.get("cost_usd", 0.0) for item in interactions)
            total_duration = sum(item.get("latency_ms", 0.0) for item in interactions)

            session = TestSessionRead(
                id=sid,
                project_id=UUID("00000000-0000-0000-0000-000000000001"),
                session_name=data.get("session_name", fixture_file.stem),
                mode=data.get("mode", "replay"),
                status=SessionStatusEnum.PASSED,
                duration_ms=total_duration,
                total_interactions=len(interactions),
                total_tokens=total_tokens,
                total_cost_usd=total_cost,
                fixture_storage_path=str(fixture_file),
                metadata=data.get("metadata", {}),
                created_at=dt,
            )
            sessions.append(session)
        except Exception:
            continue

    return sorted(sessions, key=lambda s: s.created_at, reverse=True)


@router.get("", response_model=list[TestSessionRead], status_code=status.HTTP_200_OK)
def list_sessions(
    project_id: UUID | None = None,
    session_status: SessionStatusEnum | None = Query(None, alias="status"),  # noqa: B008
    mode: str | None = None,
    limit: int = Query(50, ge=1, le=500),  # noqa: B008
    offset: int = Query(0, ge=0),  # noqa: B008
) -> list[TestSessionRead]:
    """Retrieve test sessions, either from Supabase PostgreSQL or local fixtures."""
    settings = get_settings()

    if settings.is_local_mode:
        fixtures_path = settings.get_resolved_fixtures_dir()
        sessions = _load_local_sessions(fixtures_path)

        if session_status:
            sessions = [s for s in sessions if s.status == session_status]
        if mode:
            sessions = [s for s in sessions if s.mode.lower() == mode.lower()]

        return sessions[offset : offset + limit]

    client = get_supabase_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase client is not available",
        )

    query = client.table("test_sessions").select("*")
    if project_id:
        query = query.eq("project_id", str(project_id))
    if session_status:
        query = query.eq("status", session_status.value)
    if mode:
        query = query.eq("mode", mode)

    response = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    records = extract_records(response.data)
    return [TestSessionRead(**item) for item in records]


@router.post("", response_model=TestSessionRead, status_code=status.HTTP_201_CREATED)
def create_session(payload: TestSessionCreate) -> TestSessionRead:
    """Record a test session run in the database."""
    settings = get_settings()

    if settings.is_local_mode:
        return TestSessionRead(
            id=uuid4(),
            project_id=payload.project_id or UUID("00000000-0000-0000-0000-000000000001"),
            session_name=payload.session_name,
            mode=payload.mode,
            status=payload.status,
            duration_ms=payload.duration_ms,
            total_interactions=payload.total_interactions,
            total_tokens=payload.total_tokens,
            total_cost_usd=payload.total_cost_usd,
            fixture_storage_path=payload.fixture_storage_path,
            metadata=payload.metadata,
            created_at=datetime.now(timezone.utc),
        )

    client = get_supabase_admin_client() or get_supabase_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not available",
        )

    record = payload.model_dump(mode="json", exclude_none=True)
    if "project_id" in record and record["project_id"] is not None:
        record["project_id"] = str(record["project_id"])
    else:
        # Resolve to existing project or create a default project
        proj_res = client.table("projects").select("id").limit(1).execute()
        proj_records = extract_records(proj_res.data)
        if proj_records:
            record["project_id"] = str(proj_records[0]["id"])
        else:
            org_res = client.table("organizations").select("id").limit(1).execute()
            org_records = extract_records(org_res.data)
            if org_records:
                org_id = str(org_records[0]["id"])
                new_proj = (
                    client.table("projects")
                    .insert(
                        {
                            "org_id": org_id,
                            "name": "Default Project",
                            "slug": "default-project",
                        }
                    )
                    .execute()
                )
                new_proj_records = extract_records(new_proj.data)
                if new_proj_records:
                    record["project_id"] = str(new_proj_records[0]["id"])

    try:
        response = client.table("test_sessions").insert(record).execute()
        records = extract_records(response.data)
        if not records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to record test session",
            )
        return TestSessionRead(**records[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error recording test session: {e}",
        ) from e


@router.get("/{session_id}", response_model=TestSessionRead, status_code=status.HTTP_200_OK)
def get_session(session_id: UUID) -> TestSessionRead:
    """Retrieve a specific test session by its unique ID."""
    settings = get_settings()

    if settings.is_local_mode:
        fixtures_path = settings.get_resolved_fixtures_dir()
        sessions = _load_local_sessions(fixtures_path)
        for s in sessions:
            if s.id == session_id:
                return s
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test session with ID '{session_id}' not found",
        )

    client = get_supabase_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase client is not available",
        )

    response = client.table("test_sessions").select("*").eq("id", str(session_id)).execute()
    records = extract_records(response.data)
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test session with ID '{session_id}' not found",
        )

    return TestSessionRead(**records[0])


@router.post("/sync", response_model=FixtureSyncResponse, status_code=status.HTTP_200_OK)
def sync_fixtures(payload: FixtureSyncRequest) -> FixtureSyncResponse:
    """Ingest and synchronize recording fixtures into the backend database."""
    settings = get_settings()
    synced_sessions = 0
    synced_interactions = 0
    errors: list[str] = []

    if settings.is_local_mode:
        # Save fixtures to local disk
        fixtures_dir = settings.get_resolved_fixtures_dir()
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        for fixture in payload.fixtures:
            name = fixture.get("session_name", f"session_{uuid4().hex[:8]}")
            path = fixtures_dir / f"{name}.json"
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(fixture, f, indent=2)
                synced_sessions += 1
                synced_interactions += len(fixture.get("interactions", []))
            except Exception as e:
                errors.append(f"Failed to write fixture {name}: {e}")

        return FixtureSyncResponse(
            synced_sessions=synced_sessions,
            synced_interactions=synced_interactions,
            errors=errors,
            status="success" if not errors else "partial_success",
        )

    client = get_supabase_admin_client() or get_supabase_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not available",
        )

    # In cloud mode, find or create the project for this sync
    project_slug = payload.project_slug or "default-project"
    proj_res = client.table("projects").select("id").eq("slug", project_slug).execute()
    proj_records = extract_records(proj_res.data)
    project_id: str | None = None
    if proj_records:
        project_id = str(proj_records[0]["id"])
    else:
        # Create a default project
        org_res = client.table("organizations").select("id").limit(1).execute()
        org_records = extract_records(org_res.data)
        if org_records:
            org_id = str(org_records[0]["id"])
            new_proj = (
                client.table("projects")
                .insert(
                    {
                        "org_id": org_id,
                        "name": project_slug.replace("-", " ").title(),
                        "slug": project_slug,
                    }
                )
                .execute()
            )
            new_proj_records = extract_records(new_proj.data)
            if new_proj_records:
                project_id = str(new_proj_records[0]["id"])

    for fixture in payload.fixtures:
        session_name = fixture.get("session_name", f"session_{uuid4().hex[:8]}")
        interactions = fixture.get("interactions", [])
        total_tokens = sum(
            (item.get("prompt_tokens", 0) + item.get("completion_tokens", 0))
            for item in interactions
        )
        total_cost = sum(item.get("cost_usd", 0.0) for item in interactions)
        total_duration = sum(item.get("latency_ms", 0.0) for item in interactions)

        session_record = {
            "session_name": session_name,
            "mode": fixture.get("mode", "auto"),
            "status": "passed",
            "duration_ms": total_duration,
            "total_interactions": len(interactions),
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost,
            "metadata": fixture.get("metadata", {}),
        }
        if project_id:
            session_record["project_id"] = project_id

        try:
            sess_insert = client.table("test_sessions").insert(session_record).execute()
            sess_records = extract_records(sess_insert.data)
            if sess_records:
                created_session_id = str(sess_records[0]["id"])
                synced_sessions += 1

                # Ingest individual interactions
                interaction_records = []
                for idx, inter in enumerate(interactions):
                    interaction_records.append(
                        {
                            "session_id": created_session_id,
                            "step_index": idx,
                            "provider": inter.get("provider", "unknown"),
                            "model": inter.get("model", "unknown"),
                            "prompt_tokens": inter.get("prompt_tokens", 0),
                            "completion_tokens": inter.get("completion_tokens", 0),
                            "cost_usd": inter.get("cost_usd", 0.0),
                            "latency_ms": inter.get("latency_ms", 0.0),
                            "request_payload": inter.get("request", {}),
                            "response_payload": inter.get("response", {}),
                        }
                    )

                if interaction_records:
                    client.table("interactions").insert(interaction_records).execute()
                    synced_interactions += len(interaction_records)
        except Exception as e:
            errors.append(f"Failed to sync session '{session_name}': {e}")

    return FixtureSyncResponse(
        synced_sessions=synced_sessions,
        synced_interactions=synced_interactions,
        errors=errors,
        status="success" if not errors else "partial_success",
    )
