"""Interactions and LLM call timeline API endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, status

from ...config import get_settings
from ...db.client import extract_records, get_supabase_client
from ...db.models import InteractionRead

router = APIRouter(prefix="/interactions", tags=["Interactions"])


@router.get("", response_model=list[InteractionRead], status_code=status.HTTP_200_OK)
def list_interactions(
    session_id: UUID | None = None,
    limit: int = Query(100, ge=1, le=500),  # noqa: B008
    offset: int = Query(0, ge=0),  # noqa: B008
) -> list[InteractionRead]:
    """Retrieve recorded LLM interaction events with request/response payloads."""
    settings = get_settings()

    if settings.is_local_mode:
        fixtures_path = settings.get_resolved_fixtures_dir()
        interactions: list[InteractionRead] = []

        if not fixtures_path.exists():
            return interactions

        for fixture_file in fixtures_path.glob("*.json"):
            try:
                with open(fixture_file, encoding="utf-8") as f:
                    data = json.load(f)

                curr_sid_raw = data.get("session_id")
                try:
                    curr_sid = UUID(curr_sid_raw) if curr_sid_raw else uuid4()
                except ValueError:
                    curr_sid = uuid4()

                if session_id and curr_sid != session_id:
                    continue

                for idx, inter in enumerate(data.get("interactions", [])):
                    interactions.append(
                        InteractionRead(
                            id=uuid4(),
                            session_id=curr_sid,
                            step_index=inter.get("step_index", idx),
                            provider=inter.get("provider", "openai"),
                            model=inter.get("model", "gpt-4o"),
                            prompt_tokens=inter.get("prompt_tokens", 0),
                            completion_tokens=inter.get("completion_tokens", 0),
                            cost_usd=inter.get("cost_usd", 0.0),
                            latency_ms=inter.get("latency_ms", 0.0),
                            request_payload=inter.get("request", {}),
                            response_payload=inter.get("response", {}),
                            created_at=datetime.now(timezone.utc),
                        )
                    )
            except Exception:
                continue

        return interactions[offset : offset + limit]

    client = get_supabase_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase client is not available",
        )

    query = client.table("interactions").select("*")
    if session_id:
        query = query.eq("session_id", str(session_id))

    response = query.order("step_index", desc=False).range(offset, offset + limit - 1).execute()
    records = extract_records(response.data)
    return [InteractionRead(**item) for item in records]


@router.get("/{interaction_id}", response_model=InteractionRead, status_code=status.HTTP_200_OK)
def get_interaction(interaction_id: UUID) -> InteractionRead:
    """Retrieve full request and response payloads for a single interaction."""
    settings = get_settings()

    if settings.is_local_mode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interaction '{interaction_id}' not found in local mode",
        )

    client = get_supabase_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase client is not available",
        )

    response = client.table("interactions").select("*").eq("id", str(interaction_id)).execute()
    records = extract_records(response.data)
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interaction with ID '{interaction_id}' not found",
        )

    return InteractionRead(**records[0])
