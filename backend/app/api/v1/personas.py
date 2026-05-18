"""Buyer Persona Generation API.

Generates detailed buyer personas for one or all ICPs associated with a
company.  Personas feed directly into the outreach generation stage.

Endpoints:
  POST /personas/generate      — run PersonaAgent for a company's ICPs;
                                 optionally filter to a single ICP.
  GET  /personas/{company_id}  — retrieve all stored personas.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.core.dependencies import DbSession
from app.db.repositories import CompanyRepository, ICPRepository, PersonaRepository
from app.agents import PersonaAgent
from app.schemas.company import CompanyAnalysis, CompanyInput
from app.schemas.icp import ICPProfile
from app.schemas.persona import PersonaGenerateRequest

router = APIRouter(prefix="/personas", tags=["Persona Generation"])


@router.post(
    "/generate",
    summary="Generate buyer personas for an ICP",
)
async def generate_personas(payload: PersonaGenerateRequest, db: DbSession) -> dict:
    """POST /personas/generate

    Runs PersonaAgent to produce detailed buyer personas.  Requires that
    the ICP generation step (POST /icp/generate) has been completed first.

    Request body (PersonaGenerateRequest):
      company_id      (UUID) : Target company.
      icp_id          (UUID, optional) : If provided, generate personas
                               only for this specific ICP; otherwise all
                               company ICPs are used.
      num_personas    (int)  : Personas per ICP (default controlled by schema).

    The agent is given access to the Qdrant gap collection for RAG context
    so personas can reference specific market opportunities.

    Returns a flat list of all generated personas across all targeted ICPs.
    """
    # ---- Load prerequisites ----
    comp_repo = CompanyRepository(db)
    record = await comp_repo.get_by_id(payload.company_id)
    if not record or not record.analysis:
        raise HTTPException(status_code=404, detail="Company analysis not found")

    inp = CompanyInput(**record.input_data)
    analysis = CompanyAnalysis(**{**record.analysis, "raw_input": inp})

    # ---- Load and optionally filter ICPs ----
    icp_repo = ICPRepository(db)
    icp_records = await icp_repo.get_by_company(payload.company_id)
    if not icp_records:
        raise HTTPException(status_code=404, detail="No ICPs found. Run /icp/generate first.")

    icps = [ICPProfile(**r.profile_data) for r in icp_records]
    if payload.icp_id:
        # Filter to the requested ICP; 404 if it doesn't belong to this company
        icps = [i for i in icps if str(i.icp_id) == str(payload.icp_id)]
        if not icps:
            raise HTTPException(status_code=404, detail="Requested ICP not found for company")

    # ---- Run PersonaAgent ----
    personas = await PersonaAgent().run(
        company_analysis=analysis,
        icps=icps,
        num_personas_per_icp=payload.num_personas,
        rag_collection=f"gap_{payload.company_id}",
    )

    persona_repo = PersonaRepository(db)
    for p in personas:
        await persona_repo.create(
            icp_id=p.icp_id,
            company_id=payload.company_id,
            persona_data=p.model_dump(mode="json"),
        )

    return {
        "company_id": str(payload.company_id),
        "total": len(personas),
        "personas": [p.model_dump(mode="json") for p in personas],
    }


@router.get("/{company_id}", summary="Get personas for a company")
async def get_personas(company_id: uuid.UUID, db: DbSession) -> dict:
    """GET /personas/{company_id}

    Returns all stored persona_data dicts for the company.
    Empty list if no personas have been generated yet.
    """
    repo = PersonaRepository(db)
    records = await repo.get_by_company(company_id)
    return {
        "company_id": str(company_id),
        "total": len(records),
        "personas": [r.persona_data for r in records],
    }
