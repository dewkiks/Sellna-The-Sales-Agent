"""webscraper — generic web-scraping engine.

A standalone scraping subsystem, separate from the social-media scraper in
``scrapping_module/``. It powers the pipeline's WebAgent (via
``app/services/scraping_service.py``) and the ``POST /scrapers/web`` endpoint.

Modules:
  config     — engine configuration (timeouts, retries, user-agent pool),
               overridable via environment variables.
  scraper    — async fetch engine: httpx for static pages, Playwright for
               JavaScript-rendered pages, with retry/backoff + anti-bot handling.
  extractor  — parses raw HTML into a structured dict (title, meta, body text,
               headings, links, tables, JSON-LD).
"""
