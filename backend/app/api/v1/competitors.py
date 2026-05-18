"""Competitor Discovery & Web Intelligence API.

Manages the discovery and enrichment of competitor data for a given company.
This module covers stages 2–4 of the standalone pipeline flow: discovering
competitors via LLM reasoning (CompetitorAgent), scraping their websites
(WebAgent), and cleaning/normalising the raw scraped content (CleaningAgent).

Endpoints:
  POST /competitors/discover/{company_id}
       — Run CompetitorAgent to identify competitors; persist to Postgres.
  GET  /competitors/{company_id}
       — Return all stored competitors with their web and clean data.
  POST /competitors/scrape/{company_id}
       — Run WebAgent + CleaningAgent on all discovered competitors;
         update records with raw web data and cleaned structured data.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.core.dependencies import DbSession
from app.db.repositories import CompanyRepository, CompetitorRepository
from app.agents import CompetitorAgent, WebAgent, CleaningAgent
from app.schemas.company import CompanyAnalysis

router = APIRouter(prefix="/competitors", tags=["Competitive Intelligence"])


@router.post(
    "/discover/{company_id}",
    summary="Discover competitors for a company",
)
async def discover_competitors(company_id: uuid.UUID, db: DbSession) -> dict:
    """POST /competitors/discover/{company_id}

    Runs CompetitorAgent against an already-analyzed company and saves
    the discovered competitors to Postgres.

    Requires that POST /company/input has been called first — raises 404
    if the company or its analysis is missing.

    Returns:
      total       (int) : Number of competitors found.
      competitors (list): Each entry has name, website, category,
                          positioning, and relevance_score.
    """
    company_repo = CompanyRepository(db)
    record = await company_repo.get_by_id(company_id)
    if not record or not record.analysis:
        raise HTTPException(status_code=404, detail="Company or analysis not found")

    # Reconstruct typed schema objects from the JSON stored in Postgres.
    # The stored dict lacks the nested `raw_input` object, so we rebuild it.
    from app.schemas.company import CompanyInput
    inp = CompanyInput(**record.input_data)
    analysis = CompanyAnalysis(**{**record.analysis, "raw_input": inp})

    competitors = await CompetitorAgent().run(analysis)

    comp_repo = CompetitorRepository(db)
    await comp_repo.bulk_create(
        company_id=company_id,
        competitors=[
            {
                "name": c.name,
                "website": c.website,
                "category": c.category,
                "positioning": c.positioning,
                "relevance_score": c.relevance_score,
            }
            for c in competitors
        ],
    )

    return {
        "company_id": str(company_id),
        "total": len(competitors),
        "competitors": [c.model_dump(mode="json") for c in competitors],
    }


@router.get(
    "/{company_id}",
    summary="Get all competitors for a company",
)
async def get_competitors(company_id: uuid.UUID, db: DbSession) -> dict:
    """GET /competitors/{company_id}

    Returns all competitor records for the company.  Each record includes
    flags indicating whether web_data and clean_data have been populated
    (i.e. whether the scrape stage has been run).
    """
    comp_repo = CompetitorRepository(db)
    records = await comp_repo.get_by_company(company_id)
    return {
        "company_id": str(company_id),
        "total": len(records),
        "competitors": [
            {
                "id": str(r.id),
                "name": r.name,
                "website": r.website,
                "category": r.category,
                "positioning": r.positioning,
                "relevance_score": r.relevance_score,
                "has_web_data": r.web_data is not None,
                "has_clean_data": r.clean_data is not None,
                "web_data": r.web_data,
                "clean_data": r.clean_data,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ],
    }


@router.post(
    "/scrape/{company_id}",
    summary="Scrape competitor websites and clean data",
)
async def scrape_competitors(
    company_id: uuid.UUID,
    db: DbSession,
    render_js: bool = False,
) -> dict:
    """POST /competitors/scrape/{company_id}

    Runs two agents in sequence for every competitor already stored:
      1. WebAgent — fetches each competitor's website (optionally via
         headless browser when `render_js=true`).
      2. CleaningAgent — normalises the raw HTML/text into structured data.

    Both raw web_data and cleaned clean_data are written back to Postgres.

    Query param:
      render_js (bool, default False) — enable Playwright-based JS rendering
      for SPAs that don't serve content in plain HTML.

    Returns a summary with `scraped` / `failed` counts and the cleaned data.
    Raises 404 if no competitors have been discovered yet.
    """
    comp_repo = CompetitorRepository(db)
    records = await comp_repo.get_by_company(company_id)
    if not records:
        raise HTTPException(status_code=404, detail="No competitors found. Run /discover first.")

    from app.schemas.competitor import CompetitorDiscovered
    competitors = [
        CompetitorDiscovered(
            competitor_id=r.id,
            name=r.name,
            website=r.website,
            category=r.category,
            positioning=r.positioning,
            relevance_score=r.relevance_score,
        )
        for r in records
    ]

    web_data = await WebAgent(render_js=render_js).run(competitors)
    clean_data = await CleaningAgent().run(web_data)

    # Persist both result layers so downstream queries can access either
    # raw or cleaned representations without re-running the agents.
    for wd, cd in zip(web_data, clean_data):
        await comp_repo.update_web_data(wd.competitor_id, wd.model_dump(mode="json"))
        await comp_repo.update_clean_data(cd.competitor_id, cd.model_dump(mode="json"))

    return {
        "scraped": sum(1 for w in web_data if w.scrape_success),
        "failed": sum(1 for w in web_data if not w.scrape_success),
        "competitors": [cd.model_dump(mode="json") for cd in clean_data],
    }
