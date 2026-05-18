"""Standalone FastAPI service exposing the scraping engine over HTTP.

This file serves two purposes:

  1. Development / local use: run `python scraper_standalone.py` (or
     `uvicorn scraper_standalone:app`) to get a self-contained scraping API
     with a browser UI at http://localhost:8000.

  2. Microservice deployment: the main Sellna.ai FastAPI application
     (main.py) can call this service's endpoints via HTTP rather than
     importing scraper.py directly, allowing the scraping workload to be
     isolated in a separate process or container.

Endpoints:
  GET  /                    Serves the static HTML UI (static/index.html).
  POST /api/scrape          Batch-scrape URLs; returns structured extracted data.
  POST /api/social/scrape   Batch-scrape social-media profiles (LinkedIn/Instagram).
  POST /api/export/csv      Convert a ScrapeResponse to a downloadable CSV file.
"""

from __future__ import annotations

import io
import csv
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from webscraper.extractor import extract
from webscraper.scraper import Scraper
from scrapping_module.social import SocialScraper

app = FastAPI(title="Web Scraping Module", description="Advanced multi-engine web content extractor")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------

class ScrapeRequest(BaseModel):
    """Request body for the /api/scrape endpoint.

    Attributes:
        urls:      List of absolute URLs to fetch and extract.
        proxy:     Optional proxy URL (e.g. "http://user:pass@host:port").
                   Forwarded to both httpx and Playwright.
        render_js: If True, every URL is fetched via headless Playwright
                   instead of httpx (forces JS rendering for all pages).
    """
    urls: list[str]
    proxy: str | None = None
    render_js: bool = False


class ResultItem(BaseModel):
    """Outcome for a single URL within a scrape batch.

    Attributes:
        url:            Final URL (after redirects).
        status:         HTTP status code.
        success:        True when data was successfully extracted.
        data:           Structured dict from extractor.extract() (on success).
        error:          Error message string (on failure).
        redirect_chain: Intermediate redirect URLs.
        elapsed_ms:     Total fetch time in milliseconds.
        rendered:       True when Playwright was used.
    """
    url: str
    status: int
    success: bool
    data: dict | None = None
    error: str | None = None
    redirect_chain: list[str]
    elapsed_ms: float
    rendered: bool = False


class ScrapeResponse(BaseModel):
    """Aggregated response for a batch scrape operation."""
    results: list[ResultItem]
    total: int
    successful: int
    failed: int


class SocialScrapeRequest(BaseModel):
    """Request body for the /api/social/scrape endpoint.

    Attributes:
        urls:  LinkedIn or Instagram profile URLs to scrape.
        proxy: Optional proxy URL forwarded to SocialScraper.
    """
    urls: list[str]
    proxy: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def index():
    """Serve the static HTML control panel for manual testing."""
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/scrape", response_model=ScrapeResponse)
async def scrape(req: ScrapeRequest):
    """Batch-scrape a list of URLs and return structured extracted data.

    For each URL:
      1. scraper.Scraper fetches the raw HTML (httpx, with automatic Playwright
         fallback if the site blocks plain HTTP requests).
      2. extractor.extract() parses the HTML into title, paragraphs, links, etc.
      3. The result is packaged into a ResultItem and included in the response.

    Args:
        req: ScrapeRequest containing URLs and optional scraping options.

    Returns:
        ScrapeResponse with per-URL results and aggregate counts.
    """
    scraper = Scraper(proxy=req.proxy, render_js=req.render_js)
    raw_results = await scraper.scrape_urls(req.urls)

    items: list[ResultItem] = []
    for r in raw_results:
        if r.success:
            # Only run the HTML parser on successful fetches.
            data = extract(r.html, r.url)
            items.append(ResultItem(
                url=r.url,
                status=r.status,
                success=True,
                data=data,
                redirect_chain=r.redirect_chain,
                elapsed_ms=r.elapsed_ms,
                rendered=r.rendered
            ))
        else:
            items.append(ResultItem(
                url=r.url,
                status=r.status,
                success=False,
                error=r.error,
                redirect_chain=r.redirect_chain,
                elapsed_ms=r.elapsed_ms,
                rendered=r.rendered
            ))

    successful = sum(1 for i in items if i.success)
    return ScrapeResponse(
        results=items,
        total=len(items),
        successful=successful,
        failed=len(items) - successful,
    )


@app.post("/api/social/scrape")
async def scrape_social(req: SocialScrapeRequest):
    """Batch-scrape social-media profiles (LinkedIn and Instagram).

    Delegates to SocialScraper which runs platform-specific strategies
    concurrently in a thread pool.  See scrapping_module/social.py for the
    full strategy chain.

    Args:
        req: SocialScrapeRequest with profile URLs and optional proxy.

    Returns:
        JSON dict with results list and aggregate counts.
    """
    scraper = SocialScraper(proxy=req.proxy)
    results = await scraper.scrape_batch(req.urls)

    return {
        "results": results,
        "total": len(results),
        "successful": sum(1 for r in results if "error" not in r),
        "failed": sum(1 for r in results if "error" in r)
    }


@app.post("/api/export/csv")
async def export_csv(req: ScrapeResponse):
    """Convert a ScrapeResponse into a downloadable CSV file.

    Each successful result becomes one row: URL, status, title, meta
    description, counts of paragraphs/links/images, and elapsed time.
    Failed URLs are included as error rows so the export is complete.

    Returns:
        StreamingResponse with Content-Disposition: attachment so the browser
        triggers a file download instead of rendering the CSV inline.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Write column headers.
    writer.writerow(["URL", "Status", "Title", "Description", "Paragraphs", "Links", "Images", "Elapsed MS"])

    for r in req.results:
        if r.success and r.data is not None:
            d = r.data
            writer.writerow([
                r.url,
                r.status,
                d.get("title", ""),
                d.get("meta_description", ""),
                len(d.get("paragraphs", [])),
                len(d.get("links", [])),
                len(d.get("images", [])),
                r.elapsed_ms
            ])
        else:
            # Include failed rows so the export reflects the full batch.
            writer.writerow([r.url, f"Error: {r.error}", "", "", "", "", "", r.elapsed_ms])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=scrape_results.csv"}
    )


if __name__ == "__main__":
    uvicorn.run("scraper_standalone:app", host="0.0.0.0", port=8000, reload=True)
