"""Unit tests for ScrapingService.

ScrapingService wraps the lower-level ``Scraper`` class from the scrapping_module.
These tests mock ``Scraper`` entirely using ``unittest.mock.patch`` so no real
HTTP requests or Playwright browser sessions are launched.

Each test constructs a ``MagicMock`` that mimics the object returned by
``Scraper.scrape_urls``, then checks that ScrapingService correctly maps the
raw scrape result into the dict format consumed by agents.

Test coverage:
  - test_scrape_websites_success       : successful scrape → structured dict
                                         with "scrape_success": True and "title"
  - test_scrape_websites_failure       : failed scrape (e.g. 403) → dict with
                                         "scrape_success": False and "error"
  - test_scrape_competitor_homepage    : convenience single-URL method returns
                                         a plain dict (not a list)
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.scraping_service import ScrapingService


@pytest.mark.asyncio
async def test_scrape_websites_success():
    """Verify ScrapingService maps a successful scrape result to the expected dict shape.

    ``patch("app.services.scraping_service.Scraper")`` replaces the Scraper class
    at the module level where ScrapingService imports it, so the service never
    makes a real HTTP request.  ``MockScraper.return_value`` is the mock
    *instance* that ``Scraper()`` inside the service would return.
    """
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.html = "<html><head><title>Acme Corp</title></head><body><p>We build AI sales tools.</p></body></html>"
    mock_result.url = "https://acme.example.com"
    mock_result.elapsed_ms = 120.0
    mock_result.rendered = False

    with patch("app.services.scraping_service.Scraper") as MockScraper:
        instance = MockScraper.return_value
        instance.scrape_urls = AsyncMock(return_value=[mock_result])

        svc = ScrapingService()
        results = await svc.scrape_websites(["https://acme.example.com"])

    assert len(results) == 1
    assert results[0]["scrape_success"] is True
    assert results[0]["url"] == "https://acme.example.com"
    assert "title" in results[0]  # service should parse <title> from the HTML


@pytest.mark.asyncio
async def test_scrape_websites_failure():
    """Verify ScrapingService handles a failed scrape without raising an exception.

    A failed scrape (e.g. HTTP 403 or network timeout) should produce a result
    dict with "scrape_success": False and an "error" key, rather than crashing
    the agent that requested the scrape.
    """
    mock_result = MagicMock()
    mock_result.success = False
    mock_result.html = ""
    mock_result.url = "https://blocked.example.com"
    mock_result.error = "HTTP 403"
    mock_result.elapsed_ms = 5000.0

    with patch("app.services.scraping_service.Scraper") as MockScraper:
        instance = MockScraper.return_value
        instance.scrape_urls = AsyncMock(return_value=[mock_result])

        svc = ScrapingService()
        results = await svc.scrape_websites(["https://blocked.example.com"])

    assert len(results) == 1
    assert results[0]["scrape_success"] is False
    assert "error" in results[0]


@pytest.mark.asyncio
async def test_scrape_competitor_homepage():
    """Verify scrape_competitor_homepage returns a single dict (not a list).

    This is a convenience wrapper around scrape_websites([url]) that agents use
    when they only need to scrape one URL.  The test confirms it unwraps the
    list and returns a plain dict.
    """
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.html = "<html><title>Competitor</title><body><p>Features here.</p></body></html>"
    mock_result.url = "https://competitor.example.com"
    mock_result.elapsed_ms = 200.0
    mock_result.rendered = False

    with patch("app.services.scraping_service.Scraper") as MockScraper:
        instance = MockScraper.return_value
        instance.scrape_urls = AsyncMock(return_value=[mock_result])

        svc = ScrapingService()
        result = await svc.scrape_competitor_homepage("https://competitor.example.com")

    assert isinstance(result, dict)
    assert result.get("scrape_success") is True
