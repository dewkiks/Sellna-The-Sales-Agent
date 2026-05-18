"""Company Intelligence API — list and delete stored companies.

A company record is created by the pipeline (POST /pipeline/run); the
`company_id` UUID it produces is the foreign key used by every other
module (competitors, ICPs, personas, outreach). This module lets the
frontend enumerate those companies and remove them.

Endpoints:
  GET    /company/      — list all companies stored in the DB
  DELETE /company/{id}  — hard-delete a company + all derived data
                          (Postgres rows and its Qdrant vector collection)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.core.dependencies import DbSession
from app.core.logging import get_logger
from app.db.repositories import CompanyRepository
from app.db.vector_store import get_vector_store

router = APIRouter(prefix="/company", tags=["Company Intelligence"])
logger = get_logger(__name__)


@router.get(
    "/",
    summary="List all companies",
)
async def list_companies(db: DbSession) -> dict:
    """GET /company/ — Returns a summary list of every company in the DB.

    Each entry includes whether a domain analysis has been stored yet
    (`has_analysis`), allowing the frontend to indicate incomplete records.
    """
    repo = CompanyRepository(db)
    records = await repo.list_all()
    return {
        "total": len(records),
        "companies": [
            {
                "id": str(r.id),
                "name": r.name,
                "industry": r.industry,
                "created_at": r.created_at.isoformat(),
                "has_analysis": r.analysis is not None,
            }
            for r in records
        ],
    }


@router.delete(
    "/{company_id}",
    summary="Delete a company and all of its data (Postgres + Qdrant)",
)
async def delete_company(company_id: uuid.UUID, db: DbSession) -> dict:
    """Permanently remove a company and every record derived from it —
    competitors, ICPs, personas, outreach assets, market gaps and social
    intelligence — plus its gap-analysis vector collection in Qdrant.
    """
    repo = CompanyRepository(db)
    deleted = await repo.delete(company_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Company not found")

    # Drop the company's RAG vector collection (best-effort).
    # The collection is named "gap_<company_id>" and holds embeddings produced
    # by GapAnalysisAgent.  Failure here is logged but does NOT abort the
    # response — the Postgres records are already deleted and the orphaned
    # Qdrant collection is harmless noise at worst.
    try:
        await get_vector_store().delete_collection(f"gap_{company_id}")
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "api.company.delete.vector_failed", company_id=str(company_id), error=str(e)
        )

    logger.info("api.company.deleted", company_id=str(company_id))
    return {"company_id": str(company_id), "status": "deleted"}


@router.post(
    "/wipe-all",
    summary="Delete ALL data — every company, Postgres row and Qdrant collection",
)
async def wipe_all_data(db: DbSession) -> dict:
    """Destructive maintenance endpoint — truncates every application table and
    drops every Qdrant collection. Powers the in-app 'Clear all data' action.
    """
    repo = CompanyRepository(db)
    await repo.delete_all()

    collections = 0
    try:
        collections = await get_vector_store().delete_all_collections()
    except Exception as e:  # noqa: BLE001
        logger.warning("api.company.wipe.vector_failed", error=str(e))

    logger.info("api.company.wiped", qdrant_collections=collections)
    return {"status": "wiped", "qdrant_collections_deleted": collections}
