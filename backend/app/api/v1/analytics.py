"""Analytics & Performance API.

Reports on how a company's outreach assets have performed.

Endpoint:
  GET /analytics/performance/{company_id}
      — Aggregate open/reply/conversion rates by channel and produce
        a 6-week time-series so the frontend can render trend charts.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from app.core.dependencies import DbSession
from app.db.repositories import OutreachRepository

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "/performance/{company_id}",
    summary="Get outreach performance analytics for a company",
)
async def get_performance(company_id: uuid.UUID, db: DbSession) -> dict:
    """GET /analytics/performance/{company_id}

    Returns two views of outreach performance for a company:
      - `by_channel`: averaged open/reply/conversion rates per channel
        (e.g. "email", "linkedin", "call").
      - `weekly`: a 6-week time-series bucketed by Monday of each week,
        useful for trend charts in the frontend dashboard.

    Raises 404 if no outreach assets exist for the company.
    """
    repo = OutreachRepository(db)
    records = await repo.get_by_company(company_id)
    if not records:
        raise HTTPException(status_code=404, detail="No outreach data found")

    # ---- Build per-channel aggregates ----
    # Accumulate raw sums first; divide once at the end to get averages.
    by_channel: dict[str, dict] = {}
    for r in records:
        ch = r.channel
        if ch not in by_channel:
            by_channel[ch] = {"count": 0, "open_rate": 0.0, "reply_rate": 0.0, "conversion_rate": 0.0}
        by_channel[ch]["count"] += 1
        by_channel[ch]["open_rate"] += r.open_rate
        by_channel[ch]["reply_rate"] += r.reply_rate
        by_channel[ch]["conversion_rate"] += r.conversion_rate

    # Average rates — divide accumulated sums by asset count per channel
    for ch, stats in by_channel.items():
        n = stats["count"]
        stats["avg_open_rate"] = round(stats.pop("open_rate") / n, 3)
        stats["avg_reply_rate"] = round(stats.pop("reply_rate") / n, 3)
        stats["avg_conversion_rate"] = round(stats.pop("conversion_rate") / n, 3)

    # ---- Build 6-week time-series ----
    # Pre-create 6 Monday-aligned buckets (weeks 5 → 0 weeks ago) so the
    # response always contains all 6 data points even if some weeks have no data.
    now = datetime.now(timezone.utc)
    # Align to week boundaries (Monday) — timedelta(days=weekday()) rewinds to Monday
    start = (now - timedelta(weeks=5)).replace(hour=0, minute=0, second=0, microsecond=0)
    start = start - timedelta(days=start.weekday())
    buckets: dict[str, dict] = {}
    for i in range(6):
        wk = (start + timedelta(weeks=i)).date().isoformat()
        buckets[wk] = {"week_start": wk, "assets": 0, "avg_open_rate": 0.0, "avg_reply_rate": 0.0, "avg_conversion_rate": 0.0}

    # Accumulate per-week sums; assets outside the 6-week window are silently skipped.
    sums: dict[str, dict] = {k: {"assets": 0, "open": 0.0, "reply": 0.0, "conv": 0.0} for k in buckets.keys()}
    for r in records:
        created = r.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        wk_start = created.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=created.weekday())
        wk_key = wk_start.date().isoformat()
        if wk_key not in sums:
            continue
        sums[wk_key]["assets"] += 1
        sums[wk_key]["open"] += r.open_rate
        sums[wk_key]["reply"] += r.reply_rate
        sums[wk_key]["conv"] += r.conversion_rate

    weekly: list[dict] = []
    for wk, agg in sorted(sums.items(), key=lambda kv: kv[0]):
        n = agg["assets"]
        weekly.append(
            {
                "week_start": wk,
                "assets": n,
                "avg_open_rate": round((agg["open"] / n), 3) if n else 0.0,
                "avg_reply_rate": round((agg["reply"] / n), 3) if n else 0.0,
                "avg_conversion_rate": round((agg["conv"] / n), 3) if n else 0.0,
            }
        )

    return {
        "company_id": str(company_id),
        "total_assets": len(records),
        "by_channel": by_channel,
        "weekly": weekly,
    }
