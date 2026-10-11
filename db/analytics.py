"""
db/analytics.py

Computed analytics layer for the AI Gateway SaaS dashboard.

All KPIs are derived from the persistent ``request_logs`` table — no
in-memory state is required.  Results are returned as Pydantic V2 models
so FastAPI serialises them to JSON automatically.

Available queries:
  - get_summary_stats()         → headline KPIs for the top stats strip
  - get_hourly_usage()          → 24 h histogram for the time-series chart
  - get_category_breakdown()    → cost + count per prompt category
  - get_recent_logs()           → last N request log entries for the log panel
  - get_latency_percentiles()   → p50 / p95 / p99 split by backend
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field, computed_field
from sqlalchemy import func, select, case, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.engine import get_db_session
from db.models import RequestLog, COST_LLAMA_8B_PER_1K

logger = logging.getLogger(__name__)


# ── Pydantic V2 response schemas ──────────────────────────────────────────────

class RouteSplit(BaseModel):
    """Local vs remote request counts and percentages."""
    local_count: int = 0
    remote_count: int = 0
    total: int = 0
    local_pct: float = Field(default=0.0, description="% of requests handled locally")
    remote_pct: float = Field(default=0.0, description="% of requests handled remotely")
    cache_hit_count: int = 0
    cache_hit_pct: float = 0.0


class CostSummary(BaseModel):
    """Cumulative cost and savings figures."""
    total_cost_usd: float = Field(description="Total USD spent on remote API calls")
    total_savings_usd: float = Field(description="USD saved by routing locally")
    tokens_used: int = Field(description="Total remote API tokens consumed")
    tokens_saved: int = Field(description="Estimated tokens saved via local routing")
    avg_cost_per_request_usd: float = Field(default=0.0)
    theoretical_all_remote_cost_usd: float = Field(
        description="What it would have cost if every request went to Llama-8B"
    )

    @computed_field  # type: ignore[misc]
    @property
    def savings_rate_pct(self) -> float:
        """% cost reduction vs a hypothetical all-remote baseline."""
        if self.theoretical_all_remote_cost_usd == 0:
            return 0.0
        return round(
            (self.total_savings_usd / self.theoretical_all_remote_cost_usd) * 100, 2
        )


class LatencyStats(BaseModel):
    """Latency percentiles split by routing backend."""
    local_p50_ms: float = 0.0
    local_p95_ms: float = 0.0
    local_avg_ms: float = 0.0
    remote_p50_ms: float = 0.0
    remote_p95_ms: float = 0.0
    remote_avg_ms: float = 0.0
    overall_avg_ms: float = 0.0


class HourlyBucket(BaseModel):
    """One hour's worth of aggregated data for the time-series chart."""
    hour: str = Field(description="ISO-8601 hour string: YYYY-MM-DDTHH:00")
    local_count: int = 0
    remote_count: int = 0
    total_cost_usd: float = 0.0
    total_savings_usd: float = 0.0


class CategoryStat(BaseModel):
    """Per-category cost and routing breakdown."""
    category: str
    count: int
    local_count: int
    remote_count: int
    total_cost_usd: float
    total_savings_usd: float
    avg_latency_ms: float
    success_rate_pct: float


class RecentLog(BaseModel):
    """A single request log entry for the live activity feed."""
    id: str
    created_at: datetime
    task_id: str
    prompt_snippet: str = Field(description="First 120 chars of the prompt")
    category: str
    backend: str
    model_used: str
    escalation_path: str
    tokens_used: int
    tokens_saved: int
    cost_usd: float
    savings_usd: float
    elapsed_ms: int
    succeeded_validation: bool
    attempts: int
    served_from_cache: bool


class DashboardStats(BaseModel):
    """
    Complete payload for the /api/analytics/summary endpoint.
    Combines all KPI groups into a single HTTP response to minimise
    round-trips from the dashboard.
    """
    route_split: RouteSplit
    cost_summary: CostSummary
    latency: LatencyStats
    hourly_buckets: list[HourlyBucket]
    category_breakdown: list[CategoryStat]
    recent_logs: list[RecentLog]


# ── Query helpers ─────────────────────────────────────────────────────────────

async def get_summary_stats(session: AsyncSession) -> DashboardStats:
    """
    Compute all dashboard KPIs in a single async call.

    Uses four focused SQL queries instead of one giant join so the query
    planner can use the composite indexes effectively.
    """
    # ── 1. Aggregate totals ───────────────────────────────────────────────────
    agg_q = await session.execute(
        select(
            func.count(RequestLog.id).label("total"),
            func.sum(
                case((RequestLog.backend == "local", 1), else_=0)
            ).label("local_count"),
            func.sum(
                case((RequestLog.backend != "local", 1), else_=0)
            ).label("remote_count"),
            func.sum(
                case((RequestLog.served_from_cache.is_(True), 1), else_=0)
            ).label("cache_count"),
            func.coalesce(func.sum(RequestLog.tokens_used), 0).label("tokens_used"),
            func.coalesce(func.sum(RequestLog.tokens_saved), 0).label("tokens_saved"),
            func.coalesce(func.sum(RequestLog.cost_usd), 0.0).label("total_cost"),
            func.coalesce(func.sum(RequestLog.savings_usd), 0.0).label("total_savings"),
            func.coalesce(func.avg(RequestLog.elapsed_ms), 0.0).label("avg_latency"),
        )
    )
    row = agg_q.one()

    total = row.total or 0
    local_count = row.local_count or 0
    remote_count = row.remote_count or 0
    cache_count = row.cache_count or 0
    tokens_used = int(row.tokens_used or 0)
    tokens_saved = int(row.tokens_saved or 0)
    total_cost = float(row.total_cost or 0.0)
    total_savings = float(row.total_savings or 0.0)

    # Theoretical cost: every token (used + saved) billed at llama-8b rate
    all_tokens = tokens_used + tokens_saved
    theoretical_cost = round((COST_LLAMA_8B_PER_1K / 1000) * all_tokens, 6)

    route_split = RouteSplit(
        local_count=local_count,
        remote_count=remote_count,
        total=total,
        local_pct=round((local_count / total * 100) if total else 0, 1),
        remote_pct=round((remote_count / total * 100) if total else 0, 1),
        cache_hit_count=cache_count,
        cache_hit_pct=round((cache_count / total * 100) if total else 0, 1),
    )

    cost_summary = CostSummary(
        total_cost_usd=round(total_cost, 6),
        total_savings_usd=round(total_savings, 6),
        tokens_used=tokens_used,
        tokens_saved=tokens_saved,
        avg_cost_per_request_usd=round(total_cost / total, 8) if total else 0.0,
        theoretical_all_remote_cost_usd=theoretical_cost,
    )

    # ── 2. Latency split by backend ───────────────────────────────────────────
    latency_q = await session.execute(
        select(
            RequestLog.backend,
            func.avg(RequestLog.elapsed_ms).label("avg_ms"),
            # SQLite doesn't have percentile functions; we approximate
            # via ORDER BY + LIMIT for p50 / p95 in Python after fetching.
        ).group_by(RequestLog.backend)
    )
    latency_rows = {r.backend: r.avg_ms for r in latency_q}

    # For accurate percentiles we fetch the raw latency column per backend
    # and compute in Python.  This is acceptable because elapsed_ms is a
    # single lightweight integer column.
    local_lat_q = await session.execute(
        select(RequestLog.elapsed_ms)
        .where(RequestLog.backend == "local")
        .order_by(RequestLog.elapsed_ms)
    )
    remote_lat_q = await session.execute(
        select(RequestLog.elapsed_ms)
        .where(RequestLog.backend != "local")
        .order_by(RequestLog.elapsed_ms)
    )

    def _percentile(values: list[int], pct: float) -> float:
        if not values:
            return 0.0
        idx = max(0, int(len(values) * pct / 100) - 1)
        return float(values[idx])

    local_lats = [r[0] for r in local_lat_q]
    remote_lats = [r[0] for r in remote_lat_q]

    latency = LatencyStats(
        local_p50_ms=_percentile(local_lats, 50),
        local_p95_ms=_percentile(local_lats, 95),
        local_avg_ms=round(float(latency_rows.get("local", 0) or 0), 1),
        remote_p50_ms=_percentile(remote_lats, 50),
        remote_p95_ms=_percentile(remote_lats, 95),
        remote_avg_ms=round(float(latency_rows.get("fireworks", 0) or 0), 1),
        overall_avg_ms=round(float(row.avg_latency or 0), 1),
    )

    # ── 3. Hourly buckets (last 24 h) ─────────────────────────────────────────
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    hourly_q = await session.execute(
        select(RequestLog).where(RequestLog.created_at >= cutoff)
        .order_by(RequestLog.created_at)
    )
    all_recent = hourly_q.scalars().all()

    buckets: dict[str, HourlyBucket] = {}
    for entry in all_recent:
        # Bucket key = "YYYY-MM-DDTHH:00"
        ts = entry.created_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        key = ts.strftime("%Y-%m-%dT%H:00")
        if key not in buckets:
            buckets[key] = HourlyBucket(hour=key)
        b = buckets[key]
        if entry.backend == "local":
            b.local_count += 1
        else:
            b.remote_count += 1
        b.total_cost_usd = round(b.total_cost_usd + entry.cost_usd, 6)
        b.total_savings_usd = round(b.total_savings_usd + entry.savings_usd, 6)

    hourly_buckets = sorted(buckets.values(), key=lambda x: x.hour)

    # ── 4. Category breakdown ─────────────────────────────────────────────────
    cat_q = await session.execute(
        select(
            RequestLog.category,
            func.count(RequestLog.id).label("count"),
            func.sum(case((RequestLog.backend == "local", 1), else_=0)).label("local_count"),
            func.sum(case((RequestLog.backend != "local", 1), else_=0)).label("remote_count"),
            func.coalesce(func.sum(RequestLog.cost_usd), 0.0).label("cost"),
            func.coalesce(func.sum(RequestLog.savings_usd), 0.0).label("savings"),
            func.avg(RequestLog.elapsed_ms).label("avg_ms"),
            func.avg(
                case((RequestLog.succeeded_validation.is_(True), 1.0), else_=0.0)
            ).label("success_rate"),
        ).group_by(RequestLog.category)
        .order_by(func.sum(RequestLog.cost_usd).desc())
    )
    category_breakdown = [
        CategoryStat(
            category=r.category,
            count=r.count,
            local_count=r.local_count or 0,
            remote_count=r.remote_count or 0,
            total_cost_usd=round(float(r.cost or 0), 6),
            total_savings_usd=round(float(r.savings or 0), 6),
            avg_latency_ms=round(float(r.avg_ms or 0), 1),
            success_rate_pct=round(float(r.success_rate or 0) * 100, 1),
        )
        for r in cat_q
    ]

    # ── 5. Recent logs (last 50) ──────────────────────────────────────────────
    recent_q = await session.execute(
        select(RequestLog).order_by(RequestLog.created_at.desc()).limit(50)
    )
    recent_logs = [
        RecentLog(
            id=r.id,
            created_at=r.created_at,
            task_id=r.task_id,
            prompt_snippet=r.prompt[:120] + ("…" if len(r.prompt) > 120 else ""),
            category=r.category,
            backend=r.backend,
            model_used=r.model_used,
            escalation_path=r.escalation_path,
            tokens_used=r.tokens_used,
            tokens_saved=r.tokens_saved,
            cost_usd=r.cost_usd,
            savings_usd=r.savings_usd,
            elapsed_ms=r.elapsed_ms,
            succeeded_validation=r.succeeded_validation,
            attempts=r.attempts,
            served_from_cache=r.served_from_cache,
        )
        for r in recent_q.scalars()
    ]

    return DashboardStats(
        route_split=route_split,
        cost_summary=cost_summary,
        latency=latency,
        hourly_buckets=hourly_buckets,
        category_breakdown=category_breakdown,
        recent_logs=recent_logs,
    )
