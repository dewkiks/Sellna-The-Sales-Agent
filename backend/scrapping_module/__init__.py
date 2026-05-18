"""scrapping_module — social-media scraping subsystem for Sellna.ai.

This package provides platform-specific scrapers for LinkedIn and Instagram.
It is consumed by app/services/scraping_service.py, which is called by the
pipeline's SocialAgent.

Package structure:
  social.py   — High-level SocialScraper class and all scraping strategies.
  stealth.py  — Playwright browser-fingerprint masking utilities.
  engines/    — Abstract engine base class and per-platform engine classes
                (LinkedInEngine, InstagramEngine).  These are the older
                Playwright-only implementations; social.py is the current
                production path that adds httpx strategies on top.
"""
