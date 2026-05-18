"""ICP (Ideal Customer Profile) Generation API.

Covers stages 5 and 6 of the standalone flow: market-gap analysis and ICP
generation.  POST /icp/generate runs both agents in sequence and persists
their outputs so the next stage (persona generation) has data to consume.

Endpoints:
  POST /icp/generate  — run GapAnalysisAgent then ICPAgent; save results
  GET  /icp/{company_id} — retrieve stored ICPs for a company
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.core.dependencies import DbSession
from app.db.repositories import CompanyRepository, CompetitorRepository, ICPRepository, MarketGapRepository
from app.agents import GapAnalysisAgent, ICPAgent
from app.schemas.company import CompanyAnalysis, CompanyInput
from app.schemas.competitor import CompetitorCleanData
from app.schemas.icp import ICPGenerateRequest

router = APIRouter(prefix="/icp", tags=["ICP Generation"])


@router.post(
    "/generate",
    summary="Generate Ideal Customer Profiles for a company",
)
async def generate_icps(payload: ICPGenerateRequest, db: DbSession) -> dict:
    """POST /icp/generate

    Two-stage agent run — both agents must complete before the response
    is returned (this is a synchronous, blocking call):

      Stage 1 — GapAnalysisAgent:
        Uses competitor clean_data as RAG context alongside the company
        analysis to identify market gaps (pricing, features, geography,
        messaging).  Results are stored in MarketGapRecord.

      Stage 2 — ICPAgent:
        Reads the company analysis and the gaps found in stage 1 to
        generate `num_profiles` Ideal Customer Profiles.  Stored in
        ICPRecord.

    Requires:
      - Company analysis (POST /company/input completed)
    Recommends:
      - Competitor scrape (POST /competitors/scrape completed) so
        GapAnalysisAgent has clean_data to reason over. Works without it
        but produces lower-quality gaps.

    Returns both icps and market_gaps so the caller gets the full picture.
    """
    company_id = payload.company_id

    # ---- Load prerequisites from Postgres ----
    comp_repo = CompanyRepository(db)
    record = await comp_repo.get_by_id(company_id)
    if not record or not record.analysis:
        raise HTTPException(status_code=404, detail="Company analysis not found. Run /company/input first.")

    # Reconstruct typed schema objects from JSON stored in the DB
    inp = CompanyInput(**record.input_data)
    analysis = CompanyAnalysis(**{**record.analysis, "raw_input": inp})

    # Load competitor clean data for RAG — only include records that have
    # already been through the CleaningAgent (clean_data is not None)
    cc_repo = CompetitorRepository(db)
    comp_records = await cc_repo.get_by_company(company_id)
    clean_docs = [
        CompetitorCleanData(**(r.clean_data or {}))
        for r in comp_records
        if r.clean_data
    ]

    # ---- Stage 1: Gap analysis ----
    gaps = await GapAnalysisAgent().run(analysis, clean_docs)

    # Persist gaps before running ICPs so they are visible in the DB
    # even if the ICP agent subsequently fails
    gap_repo = MarketGapRepository(db)
    for gap in gaps:
        await gap_repo.create(
            company_id=company_id,
            gap_type=gap.gap_type,
            gap_data=gap.model_dump(mode="json"),
            confidence=gap.confidence_score,
        )

    # ---- Stage 2: ICP generation ----
    icps = await ICPAgent().run(analysis, gaps, payload.num_profiles)

    icp_repo = ICPRepository(db)
    for icp in icps:
        await icp_repo.create(company_id=company_id, profile_data=icp.model_dump(mode="json"))

    return {
        "company_id": str(company_id),
        "icps": [i.model_dump(mode="json") for i in icps],
        "market_gaps": [g.model_dump(mode="json") for g in gaps],
    }


@router.get(
    "/{company_id}",
    summary="Get generated ICPs for a company",
)
async def get_icps(company_id: uuid.UUID, db: DbSession) -> dict:
    """GET /icp/{company_id}

    Returns all ICP records for a company as a list of profile_data dicts.
    Empty list (not 404) when no ICPs have been generated yet.
    """
    repo = ICPRepository(db)
    records = await repo.get_by_company(company_id)
    return {
        "company_id": str(company_id),
        "total": len(records),
        "icps": [r.profile_data for r in records],
    }
