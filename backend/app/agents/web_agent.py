"""Web Intelligence Agent — pipeline stage 3.

Scrapes the homepage of each competitor discovered by CompetitorAgent and
extracts four structured data types needed by CleaningAgent and ultimately
by GapAnalysisAgent:
  - features         : heading-level text mentioning feature keywords
  - pricing_tiers    : paragraph text mentioning pricing keywords
  - marketing_copy   : page title + meta description + first h1 tags
  - value_proposition: first substantial paragraph (>60 chars)

Concurrency: all competitors are scraped in parallel via asyncio.gather,
so 5 competitors take roughly the same wall-clock time as 1.

Fallback logic: if a URL returns a 404 (e.g. the LLM provided a deep-link
URL instead of the homepage), the agent strips the path and retries with
the bare domain root.  This handles the common case where the LLM writes
"https://example.com/product" when "https://example.com" is the real homepage.

Data extraction is heuristic (keyword matching against headings/paragraphs),
not semantic.  The downstream CleaningAgent and GapAnalysisAgent's LLM call
handle the semantic interpretation.

Pipeline position: receives CompetitorDiscovered list from CompetitorAgent
(stage 2), produces CompetitorWebData list consumed by CleaningAgent (stage 5).

Key dependencies:
  - app.services.scraping_service — wrapper around scrapping_module/scraper.py
  - app.schemas.competitor — CompetitorDiscovered, CompetitorWebData
"""

from __future__ import annotations

import asyncio
import time

from app.core.logging import get_logger
from app.schemas.competitor import CompetitorDiscovered, CompetitorWebData
from app.services.scraping_service import ScrapingService

logger = get_logger(__name__)


class WebAgent:
    """Scrapes competitor websites and structures the raw extracted data.

    Proxy and JS-rendering settings are forwarded to the underlying
    ScrapingService and ultimately to the Scraper — the WebAgent itself
    holds no scraping logic.
    """

    def __init__(self, proxy: str | None = None, render_js: bool = False) -> None:
        self._scraper = ScrapingService(proxy=proxy, render_js=render_js)

    async def run(
        self, competitors: list[CompetitorDiscovered]
    ) -> list[CompetitorWebData]:
        """Scrape all competitor homepages in parallel.

        Args:
            competitors: CompetitorDiscovered list from CompetitorAgent.

        Returns:
            One CompetitorWebData per input competitor, in the same order.
            Records with scrape_success=False contain an error string and
            empty data fields; they are passed through CleaningAgent (which
            will produce empty normalized_text) without raising.
        """
        t0 = time.perf_counter()
        logger.info(
            "web_agent.start",
            module_name="WebAgent",
            input_summary=f"competitors={len(competitors)}",
        )

        tasks = [self.scrape_one(comp) for comp in competitors]
        results: list[CompetitorWebData] = await asyncio.gather(*tasks, return_exceptions=False)

        elapsed = time.perf_counter() - t0
        successful = sum(1 for r in results if r.scrape_success)
        logger.info(
            "web_agent.complete",
            module_name="WebAgent",
            execution_time=round(elapsed, 3),
            output_summary=f"scraped={successful}/{len(competitors)} sites",
        )
        return results

    async def scrape_one(self, comp: CompetitorDiscovered) -> CompetitorWebData:
        """Scrape one competitor's homepage, with a 404 fallback to the domain root.

        Args:
            comp: A single CompetitorDiscovered object with a ``website`` field.

        Returns:
            CompetitorWebData with scrape_success=True and structured fields
            on success, or scrape_success=False with an ``error`` string on failure.
        """
        website = comp.website.strip()
        if not website:
            return CompetitorWebData(
                competitor_id=comp.competitor_id,
                website=website,
                scrape_success=False,
                error="No website URL",
            )

        raw = await self._scraper.scrape_competitor_homepage(website)

        # ---- 404 fallback: strip path and retry with bare domain ----
        # The LLM sometimes generates URLs like "https://hubspot.com/crm"
        # which 404 when scrapped directly.  Retrying with "https://hubspot.com"
        # recovers the homepage content without failing the entire competitor.
        if not raw.get("scrape_success") and "404" in raw.get("error", ""):
            from urllib.parse import urlparse
            parsed = urlparse(website)
            if parsed.path and parsed.path != "/":
                base_url = f"{parsed.scheme}://{parsed.netloc}"
                logger.info(
                    "web_agent.fallback", original=website, fallback=base_url
                )
                raw = await self._scraper.scrape_competitor_homepage(base_url)
                website = base_url

        if not raw.get("scrape_success"):
            return CompetitorWebData(
                competitor_id=comp.competitor_id,
                website=website,
                scrape_success=False,
                error=raw.get("error", "Unknown scrape failure"),
            )

        # ---- Extract structured fields from the scraper's raw output ----
        headings: dict[str, list[str]] = raw.get("headings", {})
        paragraphs: list[str] = raw.get("paragraphs", [])

        # Feature extraction: h2/h3/h4 headings that contain feature-related
        # keywords.  Headings are preferred over paragraphs because they are
        # shorter, cleaner, and less likely to contain marketing filler.
        feature_kw = {"feature", "capability", "tool", "integration", "function", "module", "built"}
        features = [
            h
            for level in ("h2", "h3", "h4")
            for h in headings.get(level, [])
            if any(kw in h.lower() for kw in feature_kw)
        ][:15]

        # Pricing: paragraphs mentioning price signals.  Capped at 200 chars
        # each and 5 total to keep the downstream normalized_text compact.
        price_kw = {"pricing", "price", "plan", "per month", "per user", "free", "starter", "enterprise"}
        pricing_tiers = [
            p[:200] for p in paragraphs if any(kw in p.lower() for kw in price_kw)
        ][:5]

        # Marketing copy: the three most prominent brand-positioning signals
        # on any page — page title, meta description, and the first h1(s).
        title = raw.get("title", "")
        meta_desc = raw.get("meta_description", "")
        h1s = headings.get("h1", [])
        marketing_copy = f"{title}. {meta_desc}. {' '.join(h1s[:2])}"

        # Value proposition: the first paragraph with enough content to be
        # meaningful (>60 chars); falls back to meta_desc or title if none found.
        value_prop = next(
            (p for p in paragraphs if len(p) > 60), meta_desc or title
        )

        return CompetitorWebData(
            competitor_id=comp.competitor_id,
            website=website,
            features=features,
            pricing_tiers=pricing_tiers,
            marketing_copy=marketing_copy[:1000],
            value_proposition=value_prop[:500],
            # target_audience uses the first 3 h2 headings as a proxy for
            # the market segments the competitor explicitly addresses on the page.
            target_audience=", ".join(headings.get("h2", [])[:3]),
            raw_headings=headings,
            # Cap at 30 paragraphs — CleaningAgent further limits to 20 when
            # building normalized_text, so extra paragraphs here are never used.
            raw_paragraphs=paragraphs[:30],
            scrape_success=True,
        )
