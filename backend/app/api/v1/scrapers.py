"""Scraper API — on-demand web & social scraping with raw output.

Exposes three endpoints that allow the frontend to trigger scrapes directly
(outside the main pipeline flow) and inspect the results:

  POST /scrapers/web               — scrape any URL; return structured
                                     extraction + raw HTML (truncated to
                                     MAX_RAW_HTML bytes).
  POST /scrapers/social            — scrape a LinkedIn or Instagram profile;
                                     return parsed fields + raw scraped dict.
  GET  /scrapers/social/{company_id} — return social profiles and contacts
                                       already collected by the pipeline's
                                       Social Intelligence stage.

Implementation notes:
  - The root-level `extractor`, `scraper`, and `scrapping_module.social`
    packages live outside the `app/` directory.  This module adds the
    project root to sys.path so those imports resolve correctly.
  - Web scraping uses the `Scraper` class; JS-heavy pages can be rendered
    via Playwright by passing `render_js=True`.
  - Social scraping uses `SocialScraper` (LinkedIn / Instagram only).
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

# ---- sys.path fixup ----
# extractor, scraper, and scrapping_module live at the project root, not
# inside the app/ package.  We add the root to sys.path here so that
# `from extractor import extract` resolves regardless of how uvicorn was
# launched (mirrors the same fix in app/services/scraping_service.py).
_project_root = str(Path(__file__).parents[3].resolve())
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.dependencies import DbSession
from app.core.logging import get_logger
from app.db.repositories import SocialContactRepository, SocialProfileRepository
from webscraper.extractor import extract
from webscraper.scraper import Scraper
from scrapping_module.social import SocialScraper

router = APIRouter(prefix="/scrapers", tags=["Scrapers"])
logger = get_logger(__name__)

# Raw HTML responses are capped so a large page (e.g. 2 MB) doesn't bloat
# the JSON payload.  The response includes a `raw_html_truncated` flag so
# the caller knows the content was cut.
MAX_RAW_HTML = 400_000  # bytes (~400 KB)


class WebScrapeRequest(BaseModel):
    url: str = Field(..., description="Absolute URL of the page to scrape")
    render_js: bool = Field(
        False, description="Render JavaScript with a headless browser before extracting"
    )


class SocialScrapeRequest(BaseModel):
    url: str = Field(..., description="LinkedIn or Instagram profile URL")


def _normalize_url(url: str) -> str:
    """Trim whitespace and prepend https:// if no scheme is present.

    Raises HTTP 400 if the URL is empty after trimming.
    """
    url = (url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="A URL is required")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


@router.post("/web", summary="Scrape a web page — structured extraction + raw HTML")
async def scrape_web(payload: WebScrapeRequest) -> dict:
    """POST /scrapers/web

    Fetches a single URL using the root-level Scraper class and returns:
      - `extracted`: structured fields (title, description, main_text, links,
        etc.) produced by the `extractor.extract()` heuristic parser.
        Extraction is best-effort — an extraction failure returns `{}` rather
        than a 5xx error.
      - `raw_html`: the raw HTML bytes up to MAX_RAW_HTML; `raw_html_truncated`
        is True if the page exceeded that limit.
      - Metadata: status code, redirect chain, render mode, elapsed_ms.

    Query param `render_js=true` uses Playwright headless Chrome for SPAs.
    Raises 502 if the scraper returns no result at all.
    """
    url = _normalize_url(payload.url)
    logger.info("scraper.web.start", url=url, render_js=payload.render_js)

    scraper = Scraper(render_js=payload.render_js)
    results = await scraper.scrape_urls([url])
    result = results[0] if results else None

    if result is None:
        raise HTTPException(status_code=502, detail="Scraper returned no result")

    extracted: dict = {}
    if result.success and result.html:
        try:
            extracted = extract(result.html, result.url)
        except Exception as exc:  # extraction is best-effort; don't 500 on parser errors
            logger.warning("scraper.web.extract_failed", url=url, error=str(exc))

    raw_html = result.html or ""
    raw_bytes = len(raw_html)
    truncated = raw_bytes > MAX_RAW_HTML
    if truncated:
        raw_html = raw_html[:MAX_RAW_HTML]

    logger.info(
        "scraper.web.done", url=url, success=result.success, status=result.status
    )
    return {
        "url": result.url,
        "requested_url": url,
        "success": result.success,
        "status": result.status,
        "error": result.error or None,
        "rendered": result.rendered,
        "elapsed_ms": result.elapsed_ms,
        "redirect_chain": result.redirect_chain,
        "extracted": extracted,
        "raw_html": raw_html,
        "raw_html_truncated": truncated,
        "raw_html_bytes": raw_bytes,
    }


@router.post("/social", summary="Scrape a social profile — LinkedIn / Instagram")
async def scrape_social(payload: SocialScrapeRequest) -> dict:
    """POST /scrapers/social

    Fetches a social profile using SocialScraper and returns:
      - `profile`: the parsed fields dict (name, title, bio, etc.) when
        successful; empty dict on failure.
      - `raw`: the unmodified scraper output, useful for debugging.
      - `platform`: "LinkedIn" or "Instagram" (detected from URL).
      - `success`: True when the scraper returned data without an `error` key.

    Only LinkedIn and Instagram profile URLs are accepted; raises 400 otherwise.
    """
    url = _normalize_url(payload.url)
    lower = url.lower()
    if "linkedin.com" not in lower and "instagram.com" not in lower:
        raise HTTPException(
            status_code=400,
            detail="Only LinkedIn and Instagram profile URLs are supported",
        )

    logger.info("scraper.social.start", url=url)
    results = await SocialScraper().scrape_batch([url])
    data: dict = results[0] if results else {}

    success = bool(data) and "error" not in data
    platform = data.get("platform") or (
        "LinkedIn" if "linkedin.com" in lower else "Instagram"
    )

    logger.info("scraper.social.done", url=url, success=success, platform=platform)
    return {
        "url": url,
        "platform": platform,
        "success": success,
        "error": data.get("error"),
        "source": data.get("source"),
        "profile": data if success else {},
        "raw": data,
    }


@router.get(
    "/social/{company_id}",
    summary="Get socials, people & contacts collected by the Social Intelligence stage",
)
async def get_company_socials(company_id: uuid.UUID, db: DbSession) -> dict:
    """GET /scrapers/social/{company_id}

    Reads pipeline-persisted social intelligence data from Postgres and
    returns it grouped by "subject" (the company itself or a competitor).

    Each subject group contains:
      - profiles : social accounts (platform, url, scraped data).
      - people   : named contacts with title and LinkedIn URL.
      - emails   : email addresses found during scraping.
      - phones   : phone numbers found during scraping.

    Subject grouping key: "<subject_type>:<subject_id>" — e.g.
    "competitor:<uuid>" or "company:self".  This lets the frontend render
    a separate card per company/competitor.
    """
    profiles = await SocialProfileRepository(db).get_by_company(company_id)
    contacts = await SocialContactRepository(db).get_by_company(company_id)

    groups: dict[str, dict] = {}

    def group_for(subject_type: str, subject_id, subject_name: str) -> dict:
        # Retrieve or lazily create the group dict for this subject
        key = f"{subject_type}:{subject_id or 'self'}"
        group = groups.get(key)
        if group is None:
            group = {
                "subject_type": subject_type,
                "subject_id": str(subject_id) if subject_id else None,
                "subject_name": subject_name,
                "profiles": [],
                "people": [],
                "emails": [],
                "phones": [],
            }
            groups[key] = group
        return group

    for r in profiles:
        group_for(r.subject_type, r.subject_id, r.subject_name)["profiles"].append(
            {
                "platform": r.platform,
                "profile_type": r.profile_type,
                "url": r.url,
                "success": r.success,
                "data": r.data,
                "created_at": r.created_at.isoformat(),
            }
        )

    for c in contacts:
        group = group_for(c.subject_type, c.subject_id, c.subject_name)
        if c.kind == "email":
            group["emails"].append(c.value)
        elif c.kind == "phone":
            group["phones"].append(c.value)
        elif c.kind == "person":
            group["people"].append(
                {
                    "name": c.value,
                    "title": c.title,
                    "linkedin_url": c.url,
                    "source": c.source_page,
                }
            )

    return {
        "company_id": str(company_id),
        "total": len(profiles) + len(contacts),
        "subjects": list(groups.values()),
    }
