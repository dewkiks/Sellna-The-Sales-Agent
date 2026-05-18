"""Outreach Content Generation API.

Covers the outreach stage of the pipeline: generating channel-specific copy
(cold email, LinkedIn message, call opener) tailored to a specific buyer
persona, storing engagement feedback, and allowing manual edits to assets.

Endpoints:
  POST  /outreach/generate          — run OutreachAgent for a persona;
                                      persist generated assets.
  PATCH /outreach/asset/{asset_id}  — edit the content of a stored asset.
  GET   /outreach/{company_id}      — list all assets with their metrics.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.core.dependencies import DbSession
from app.core.logging import get_logger
from app.db.repositories import CompanyRepository, OutreachRepository, PersonaRepository
from app.agents import OutreachAgent
from app.schemas.company import CompanyAnalysis, CompanyInput
from app.schemas.outreach import (
    OutreachGenerateRequest,
    OutreachUpdateRequest,
)
from app.schemas.persona import BuyerPersona

router = APIRouter(prefix="/outreach", tags=["Outreach Generation"])
logger = get_logger(__name__)


@router.post(
    "/generate",
    summary="Generate cold email, LinkedIn, and call opener for a persona",
)
async def generate_outreach(payload: OutreachGenerateRequest, db: DbSession) -> dict:
    """POST /outreach/generate

    Generates personalised outreach copy for a specific buyer persona using
    OutreachAgent, then persists each asset (one per channel) to Postgres.

    The agent is given:
      - The buyer persona (goals, pain points, title, etc.)
      - The company analysis (value prop, differentiators)
      - A list of channels to generate copy for (e.g. ["email", "linkedin"])
      - The Qdrant RAG collection name for gap-analysis context
        (convention: "gap_<company_id>")

    Persona lookup: matches first by DB row `id`, then by `persona_data.persona_id`
    so callers can pass either identifier.

    Returns a list of `outreach_assets` — one per requested channel.
    Raises 404 if the company or persona is not found.
    """
    comp_repo = CompanyRepository(db)
    record = await comp_repo.get_by_id(payload.company_id)
    if not record or not record.analysis:
        raise HTTPException(status_code=404, detail="Company not found")

    inp = CompanyInput(**record.input_data)
    analysis = CompanyAnalysis(**{**record.analysis, "raw_input": inp})

    # ---- Locate the target persona ----
    # We try two match strategies because the caller may have the DB row id
    # OR the application-level persona_id embedded inside persona_data JSON.
    persona_repo = PersonaRepository(db)
    persona_records = await persona_repo.get_by_company(payload.company_id)
    target = next(
        (
            r for r in persona_records
            if str(r.id) == str(payload.persona_id)
            or str(r.persona_data.get("persona_id", "")) == str(payload.persona_id)
        ),
        None,
    )
    if not target:
        raise HTTPException(status_code=404, detail="Persona not found")

    persona = BuyerPersona(**target.persona_data)

    # OutreachAgent uses the Qdrant gap collection as RAG context so the
    # generated copy references specific market gaps relevant to the persona.
    assets = await OutreachAgent().run(
        persona=persona,
        analysis=analysis,
        channels=payload.channels,
        rag_collection=f"gap_{payload.company_id}",
    )

    outreach_repo = OutreachRepository(db)
    for a in assets:
        await outreach_repo.create(
            persona_id=persona.persona_id,
            company_id=payload.company_id,
            channel=a.channel,
            content=a.model_dump(mode="json"),
        )

    return {
        "company_id": str(payload.company_id),
        "persona_id": str(payload.persona_id),
        "total": len(assets),
        "outreach_assets": [a.model_dump(mode="json") for a in assets],
    }


@router.patch(
    "/asset/{asset_id}",
    summary="Edit the content of a generated outreach asset",
)
async def update_outreach_asset(
    asset_id: uuid.UUID,
    payload: OutreachUpdateRequest,
    db: DbSession,
) -> dict:
    """PATCH /outreach/asset/{asset_id}

    Allows manual editing of a generated asset's content fields (e.g.
    subject line, body, call-to-action) after the agent has run.
    Only fields present in the payload are updated (partial update).

    Raises 400 if the payload is empty.
    Raises 404 if the asset_id is unknown.
    """
    fields = payload.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    repo = OutreachRepository(db)
    record = await repo.update_content(asset_id, fields)
    if not record:
        raise HTTPException(status_code=404, detail="Outreach asset not found")

    logger.info("outreach.asset_updated", asset_id=str(asset_id), fields=list(fields))
    return {
        "id": str(record.id),
        "channel": record.channel,
        "content": record.content,
    }


@router.get("/{company_id}", summary="Get outreach assets for a company")
async def get_outreach(company_id: uuid.UUID, db: DbSession) -> dict:
    """GET /outreach/{company_id}

    Returns all outreach assets stored for the company, including their
    engagement metrics.  Assets are grouped by the persona that generated
    them (via persona_id field).
    """
    repo = OutreachRepository(db)
    records = await repo.get_by_company(company_id)
    return {
        "company_id": str(company_id),
        "total": len(records),
        "assets": [
            {
                "id": str(r.id),
                "persona_id": str(r.persona_id),
                "company_id": str(r.company_id),
                "channel": r.channel,
                "content": r.content,
                "open_rate": r.open_rate,
                "reply_rate": r.reply_rate,
                "conversion_rate": r.conversion_rate,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ],
    }
