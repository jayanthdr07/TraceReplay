"""Projects management API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status

from ...config import get_settings
from ...db.client import extract_records, get_supabase_admin_client, get_supabase_client
from ...db.models import ProjectCreate, ProjectRead

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=list[ProjectRead], status_code=status.HTTP_200_OK)
def list_projects() -> list[ProjectRead]:
    """List all configured projects."""
    settings = get_settings()

    if settings.is_local_mode:
        # In local mode, return default local workspace project
        default_id = UUID("00000000-0000-0000-0000-000000000001")
        default_org_id = UUID("00000000-0000-0000-0000-000000000000")
        return [
            ProjectRead(
                id=default_id,
                org_id=default_org_id,
                name="Local Workspace",
                slug="local-workspace",
                description="Local filesystem recording repository",
                created_at=datetime.now(timezone.utc),
            )
        ]

    client = get_supabase_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase client is not available",
        )

    response = client.table("projects").select("*").order("created_at", desc=True).execute()
    records = extract_records(response.data)
    return [ProjectRead(**item) for item in records]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate) -> ProjectRead:
    """Create a new project in the database."""
    settings = get_settings()

    target_org_id = payload.org_id

    if settings.is_local_mode:
        if target_org_id is None:
            target_org_id = UUID("00000000-0000-0000-0000-000000000000")
        return ProjectRead(
            id=uuid4(),
            org_id=target_org_id,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            created_at=datetime.now(timezone.utc),
        )

    client = get_supabase_admin_client() or get_supabase_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not available",
        )

    if target_org_id is None:
        org_res = client.table("organizations").select("id").limit(1).execute()
        existing_orgs = extract_records(org_res.data)
        if existing_orgs:
            target_org_id = UUID(str(existing_orgs[0]["id"]))
        else:
            create_org = {"name": "Default Organization", "slug": "default-org"}
            c_res = client.table("organizations").insert(create_org).execute()
            new_orgs = extract_records(c_res.data)
            if new_orgs:
                target_org_id = UUID(str(new_orgs[0]["id"]))
            else:
                target_org_id = UUID("00000000-0000-0000-0000-000000000000")

    record = {
        "org_id": str(target_org_id),
        "name": payload.name,
        "slug": payload.slug,
        "description": payload.description,
    }

    try:
        response = client.table("projects").insert(record).execute()
        records = extract_records(response.data)
        if not records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create project in database",
            )
        return ProjectRead(**records[0])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error creating project: {e}",
        ) from e


@router.get("/{project_id}", response_model=ProjectRead, status_code=status.HTTP_200_OK)
def get_project(project_id: UUID) -> ProjectRead:
    """Retrieve a project by its unique identifier."""
    settings = get_settings()

    if settings.is_local_mode:
        return ProjectRead(
            id=project_id,
            org_id=UUID("00000000-0000-0000-0000-000000000000"),
            name="Local Workspace",
            slug="local-workspace",
            description="Local filesystem recording repository",
            created_at=datetime.now(timezone.utc),
        )

    client = get_supabase_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase client is not available",
        )

    response = client.table("projects").select("*").eq("id", str(project_id)).execute()
    records = extract_records(response.data)
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found",
        )

    return ProjectRead(**records[0])
