"""Scraping Service — bridges the root-level scrapping_module into the Sales AI pipeline.

Role in architecture
--------------------
WebAgent (Stage 3) and SocialAgent (Stage 3.5) call this service to fetch and
parse competitor and company pages.  This service acts as an **adapter layer**:
it hides the implementation details of the scrapping_module from the agents and
provides a simple, typed async API.

How it bridges to the scrapping_module
---------------------------------------
The scrapping_module lives at the project root alongside the ``app/`` package.
It is *not* installed as a Python package, so ``scraping_service`` explicitly
adds the project root to ``sys.path`` (only if not already present) before
importing.  This is safe for both FastAPI uvicorn workers and Celery workers.

The three key root-level imports:
- ``scraper.Scraper``          — async httpx + optional Playwright engine;
                                 concurrently fetches a list of URLs.
- ``extractor.extract()``      — parses raw HTML into a structured dict
                                 (title, meta description, body text, links, …).
- ``scrapping_module.social.SocialScraper`` — multi-strategy scraper for
                                 LinkedIn company/person pages and Instagram.

Key parameters
--------------
- ``proxy``     — optional HTTP/SOCKS proxy URL forwarded to httpx.
- ``render_js`` — if True, Playwright is used for JavaScript-heavy pages;
                  otherwise fast httpx-only mode is used.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path so Celery worker can find top-level modules
project_root = str(Path(__file__).parent.parent.parent.resolve())
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from typing import Any

from webscraper.scraper import Scraper, ScrapeResult
from webscraper.extractor import extract
from scrapping_module.social import SocialScraper

from app.core.logging import get_logger
from app.config import get_settings

logger = get_logger(__name__)
_settings = get_settings()


class ScrapingService:
    """High-level async scraping service used by WebAgent and SocialAgent.

    A new instance is created per pipeline run (proxy/render_js may differ).
    The underlying ``Scraper`` and ``SocialScraper`` objects are created
    fresh per call so connection pools are not reused across requests.
    """

    def __init__(self, proxy: str | None = None, render_js: bool = False) -> None:
        """
        Args:
            proxy:     Optional HTTP/SOCKS proxy URL (e.g. ``socks5://host:port``).
            render_js: Enable Playwright JS rendering for dynamic pages.
                       Falls back to plain httpx when False for speed.
        """
        self.proxy = proxy
        self.render_js = render_js

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def scrape_websites(
        self, urls: list[str]
    ) -> list[dict[str, Any]]:
        """Fetch and structure a list of web pages.

        Internally, ``Scraper.scrape_urls()`` fetches all URLs concurrently
        (httpx or Playwright per URL).  For each successful result, the raw
        HTML is passed through ``extractor.extract()`` which parses it into a
        structured dict (title, description, body text, links, etc.).

        Failed URLs produce a minimal error dict rather than raising, so the
        pipeline can continue with whatever data was successfully scraped.

        Args:
            urls: List of fully-qualified URLs to fetch.

        Returns:
            One dict per URL, always including ``"scrape_success": bool``.
        """
        scraper = Scraper(proxy=self.proxy, render_js=self.render_js)
        raw: list[ScrapeResult] = await scraper.scrape_urls(urls)

        results: list[dict[str, Any]] = []
        for r in raw:
            if r.success and r.html:
                # extract() turns raw HTML into a structured intelligence dict.
                extracted = extract(r.html, r.url)
                extracted["scrape_success"] = True
                extracted["elapsed_ms"] = r.elapsed_ms
                extracted["rendered"] = r.rendered  # True if Playwright was used
                results.append(extracted)
                logger.info(
                    "scraping_service.scraped",
                    url=r.url,
                    elapsed_ms=r.elapsed_ms,
                    rendered=r.rendered,
                )
            else:
                # Preserve failed URLs in output so agents can log/skip them.
                results.append({
                    "url": r.url,
                    "scrape_success": False,
                    "error": r.error,
                    "elapsed_ms": r.elapsed_ms,
                })
                logger.warning("scraping_service.failed", url=r.url, reason=r.error)

        return results

    async def scrape_social(
        self, urls: list[str]
    ) -> list[dict[str, Any]]:
        """Scrape social media profiles (LinkedIn, Instagram).

        Delegates to ``SocialScraper.scrape_batch()`` which tries multiple
        strategies per platform (e.g. public API, direct HTTP, headless browser)
        and returns the best result available.

        Args:
            urls: Social media profile URLs to scrape.

        Returns:
            One dict per URL.  ``"url"`` key is guaranteed via ``setdefault``.
        """
        social_scraper = SocialScraper(proxy=self.proxy)
        results = await social_scraper.scrape_batch(urls)
        # Ensure every result carries its source URL for downstream correlation.
        for r, url in zip(results, urls):
            r.setdefault("url", url)
        return results

    async def scrape_competitor_homepage(self, website: str) -> dict[str, Any]:
        """Convenience wrapper — scrape a single competitor website.

        Used by WebAgent when processing competitors one at a time via
        ``asyncio.as_completed`` in the pipeline.
        """
        results = await self.scrape_websites([website])
        return results[0] if results else {"url": website, "scrape_success": False, "error": "no result"}
