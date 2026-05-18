"""Dashboard API.

Provides two read-only endpoints that aggregate live data from Postgres to
populate the frontend dashboard — no agents are invoked here.

Endpoints:
  GET /dashboard/summary  — row counts for every major entity type
                            (companies, competitors, ICPs, personas,
                            outreach assets, market gaps).
  GET /dashboard/activity — a time-sorted activity feed of recent DB
                            writes across all entity types, capped at
                            `limit` entries per type (default 20).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, select

from app.core.dependencies import DbSession
from app.db.postgres import (
    CompanyRecord,
    CompetitorRecord,
    ICPRecord,
    MarketGapRecord,
    OutreachRecord,
    PersonaRecord,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", summary="High-level dashboard counts")
async def get_summary(db: DbSession) -> dict:
    """GET /dashboard/summary

    Issues one COUNT(*) query per entity table via SQLAlchemy and returns
    the results as a single `counts` dict.  Intended for the top-of-page
    KPI cards in the frontend dashboard.
    """
    companies = (await db.execute(select(func.count()).select_from(CompanyRecord))).scalar_one()
    competitors = (await db.execute(select(func.count()).select_from(CompetitorRecord))).scalar_one()
    icps = (await db.execute(select(func.count()).select_from(ICPRecord))).scalar_one()
    personas = (await db.execute(select(func.count()).select_from(PersonaRecord))).scalar_one()
    outreach = (await db.execute(select(func.count()).select_from(OutreachRecord))).scalar_one()
    gaps = (await db.execute(select(func.count()).select_from(MarketGapRecord))).scalar_one()

    return {
        "counts": {
            "companies_analyzed": int(companies),
            "competitors_found": int(competitors),
            "icps_generated": int(icps),
            "personas_generated": int(personas),
            "outreach_assets_generated": int(outreach),
            "market_gaps_found": int(gaps),
        }
    }


@router.get("/activity", summary="Recent system activity feed")
async def get_activity(db: DbSession, limit: int = 20) -> dict:
    """GET /dashboard/activity?limit=N

    Queries the N most-recent rows from each entity table, converts them
    into uniform event dicts (type, action, target, created_at), merges
    all lists, then sorts the combined list by created_at descending and
    trims to `limit` items.

    This cross-table merge is done in Python (not SQL) because each table
    has a different schema — a UNION would require identical column sets.

    Query param:
      limit (int, 1–100, default 20) — max events to return.
    """
    limit = max(1, min(100, limit))  # clamp to safe range

    events: list[dict[str, Any]] = []

    # Companies
    company_rows = (
        await db.execute(select(CompanyRecord).order_by(CompanyRecord.created_at.desc()).limit(limit))
    ).scalars()
    for r in company_rows:
        events.append(
            {
                "type": "company",
                "action": "Company analyzed",
                "target": r.name,
                "created_at": r.created_at,
            }
        )

    # Competitors
    comp_rows = (
        await db.execute(
            select(CompetitorRecord).order_by(CompetitorRecord.created_at.desc()).limit(limit)
        )
    ).scalars()
    for r in comp_rows:
        events.append(
            {
                "type": "competitor",
                "action": "Competitor discovered",
                "target": r.name,
                "created_at": r.created_at,
            }
        )

    # ICPs
    icp_rows = (await db.execute(select(ICPRecord).order_by(ICPRecord.created_at.desc()).limit(limit))).scalars()
    for r in icp_rows:
        title = (r.profile_data or {}).get("industry") or "ICP"
        events.append(
            {
                "type": "icp",
                "action": "ICP generated",
                "target": title,
                "created_at": r.created_at,
            }
        )

    # Personas
    persona_rows = (
        await db.execute(select(PersonaRecord).order_by(PersonaRecord.created_at.desc()).limit(limit))
    ).scalars()
    for r in persona_rows:
        title = (r.persona_data or {}).get("title") or "Persona"
        events.append(
            {
                "type": "persona",
                "action": "Persona generated",
                "target": title,
                "created_at": r.created_at,
            }
        )

    # Outreach
    outreach_rows = (
        await db.execute(select(OutreachRecord).order_by(OutreachRecord.created_at.desc()).limit(limit))
    ).scalars()
    for r in outreach_rows:
        events.append(
            {
                "type": "outreach",
                "action": "Outreach generated",
                "target": r.channel,
                "created_at": r.created_at,
            }
        )

    # Gaps
    gap_rows = (
        await db.execute(select(MarketGapRecord).order_by(MarketGapRecord.created_at.desc()).limit(limit))
    ).scalars()
    for r in gap_rows:
        events.append(
            {
                "type": "gap",
                "action": "Market gap identified",
                "target": r.gap_type,
                "created_at": r.created_at,
            }
        )

    # Merge all entity event lists, sort globally, then trim to limit
    events.sort(key=lambda e: e["created_at"], reverse=True)
    events = events[:limit]

    # Serialise datetime objects to ISO-8601 strings for JSON compatibility
    def iso(dt: datetime) -> str:
        return dt.isoformat()

    return {
        "total": len(events),
        "events": [{**e, "created_at": iso(e["created_at"])} for e in events],
    }

