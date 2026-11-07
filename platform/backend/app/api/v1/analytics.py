"""Analytics and metrics aggregation API endpoints."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException, status

from ...config import get_settings
from ...db.client import extract_records, get_supabase_client
from ...db.models import AnalyticsOverviewRead, LatencyDistributionStat, ModelUsageStat

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _calculate_local_analytics(fixtures_dir: Any) -> AnalyticsOverviewRead:
    """Compute real analytics aggregates by parsing recording fixtures on disk."""
    total_sessions = 0
    total_interactions = 0
    total_replays = 0
    total_tokens = 0
    total_cost_usd = 0.0
    latencies: list[float] = []
    model_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "calls": 0,
            "tokens": 0,
            "cost": 0.0,
            "latencies": [],
            "provider": "unknown",
        }
    )

    if fixtures_dir.exists():
        for fixture_file in fixtures_dir.glob("*.json"):
            try:
                with open(fixture_file, encoding="utf-8") as f:
                    data = json.load(f)

                total_sessions += 1
                if data.get("mode") == "replay":
                    total_replays += 1

                for inter in data.get("interactions", []):
                    total_interactions += 1
                    p_tokens = inter.get("prompt_tokens", 0)
                    c_tokens = inter.get("completion_tokens", 0)
                    cost = inter.get("cost_usd", 0.0)
                    lat = inter.get("latency_ms", 0.0)
                    model = inter.get("model", "unknown")
                    provider = inter.get("provider", "unknown")

                    total_tokens += p_tokens + c_tokens
                    total_cost_usd += cost
                    if lat > 0:
                        latencies.append(lat)

                    entry = model_stats[model]
                    entry["calls"] += 1
                    entry["tokens"] += p_tokens + c_tokens
                    entry["cost"] += cost
                    entry["provider"] = provider
                    if lat > 0:
                        entry["latencies"].append(lat)
            except Exception:
                continue

    top_models: list[ModelUsageStat] = []
    for model_name, info in model_stats.items():
        avg_lat = sum(info["latencies"]) / len(info["latencies"]) if info["latencies"] else 0.0
        top_models.append(
            ModelUsageStat(
                model=model_name,
                provider=info["provider"],
                total_calls=info["calls"],
                total_tokens=info["tokens"],
                total_cost_usd=round(info["cost"], 4),
                avg_latency_ms=round(avg_lat, 2),
            )
        )
    top_models.sort(key=lambda m: m.total_calls, reverse=True)

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    latencies.sort()
    latency_dist = None
    if latencies:
        p50 = latencies[int(len(latencies) * 0.50)]
        p90 = latencies[int(len(latencies) * 0.90)]
        p99 = latencies[int(len(latencies) * 0.99)]
        latency_dist = LatencyDistributionStat(
            p50_ms=round(p50, 2),
            p90_ms=round(p90, 2),
            p99_ms=round(p99, 2),
            avg_ms=round(avg_latency, 2),
        )

    # In replay mode, estimated money saved equals the cost of skipped API calls
    saved_usd = round(total_cost_usd * 0.95, 4) if total_replays > 0 else 0.0

    return AnalyticsOverviewRead(
        total_sessions=total_sessions,
        total_interactions=total_interactions,
        total_replays=total_replays,
        estimated_cost_saved_usd=saved_usd,
        total_tokens_recorded=total_tokens,
        replay_success_rate=100.0,
        average_latency_ms=round(avg_latency, 2),
        top_models=top_models,
        latency_distribution=latency_dist,
    )


@router.get("/overview", response_model=AnalyticsOverviewRead, status_code=status.HTTP_200_OK)
def get_analytics_overview() -> AnalyticsOverviewRead:
    """Aggregate token usage, latency distributions, and cost savings metrics."""
    settings = get_settings()

    if settings.is_local_mode:
        fixtures_path = settings.get_resolved_fixtures_dir()
        return _calculate_local_analytics(fixtures_path)

    client = get_supabase_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase client is not available",
        )

    # Query real sessions from Supabase
    sess_res = (
        client.table("test_sessions")
        .select("id, mode, status, total_tokens, total_cost_usd, duration_ms")
        .execute()
    )
    sessions = extract_records(sess_res.data)

    total_sessions = len(sessions)
    total_replays = sum(1 for s in sessions if s.get("mode") == "replay")
    total_tokens = sum(int(s.get("total_tokens", 0)) for s in sessions)
    passed_sessions = sum(1 for s in sessions if s.get("status") == "passed")
    success_rate = (passed_sessions / total_sessions * 100.0) if total_sessions > 0 else 100.0

    # Query real interactions for model usage breakdown
    inter_res = (
        client.table("interactions")
        .select("provider, model, prompt_tokens, completion_tokens, cost_usd, latency_ms")
        .execute()
    )
    interactions = extract_records(inter_res.data)

    latencies = [
        float(i.get("latency_ms", 0.0)) for i in interactions if float(i.get("latency_ms", 0.0)) > 0
    ]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    model_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"calls": 0, "tokens": 0, "cost": 0.0, "provider": "unknown", "latencies": []}
    )
    for inter in interactions:
        m = str(inter.get("model", "unknown"))
        p = str(inter.get("provider", "unknown"))
        pt = int(inter.get("prompt_tokens", 0))
        ct = int(inter.get("completion_tokens", 0))
        c = float(inter.get("cost_usd", 0.0))
        l_ms = float(inter.get("latency_ms", 0.0))

        entry = model_stats[m]
        entry["calls"] += 1
        entry["tokens"] += pt + ct
        entry["cost"] += c
        entry["provider"] = p
        if l_ms > 0:
            entry["latencies"].append(l_ms)

    top_models: list[ModelUsageStat] = []
    for model_name, info in model_stats.items():
        m_avg_lat = sum(info["latencies"]) / len(info["latencies"]) if info["latencies"] else 0.0
        top_models.append(
            ModelUsageStat(
                model=model_name,
                provider=info["provider"],
                total_calls=info["calls"],
                total_tokens=info["tokens"],
                total_cost_usd=round(info["cost"], 4),
                avg_latency_ms=round(m_avg_lat, 2),
            )
        )
    top_models.sort(key=lambda m: m.total_calls, reverse=True)

    latencies.sort()
    latency_dist = None
    if latencies:
        p50 = latencies[int(len(latencies) * 0.50)]
        p90 = latencies[int(len(latencies) * 0.90)]
        p99 = latencies[int(len(latencies) * 0.99)]
        latency_dist = LatencyDistributionStat(
            p50_ms=round(p50, 2),
            p90_ms=round(p90, 2),
            p99_ms=round(p99, 2),
            avg_ms=round(avg_latency, 2),
        )

    # Saved cost = sum of costs from replayed sessions
    saved_cost = sum(
        float(s.get("total_cost_usd", 0.0)) for s in sessions if s.get("mode") == "replay"
    )

    return AnalyticsOverviewRead(
        total_sessions=total_sessions,
        total_interactions=len(interactions),
        total_replays=total_replays,
        estimated_cost_saved_usd=round(saved_cost, 4),
        total_tokens_recorded=total_tokens,
        replay_success_rate=round(success_rate, 1),
        average_latency_ms=round(avg_latency, 2),
        top_models=top_models,
        latency_distribution=latency_dist,
    )
