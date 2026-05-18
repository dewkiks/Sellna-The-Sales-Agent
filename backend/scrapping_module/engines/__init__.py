"""engines sub-package — abstract engine base class and per-platform implementations.

This package defines the original Playwright-only scraping engine hierarchy:
  base.py        — SocialEngine abstract base class (interface contract + shared utilities).
  linkedin.py    — LinkedInEngine: direct Playwright scraping of LinkedIn DOM.
  instagram.py   — InstagramEngine: Playwright scraping of Instagram profile/post pages.

Architecture note:
  These engines are the *earlier* implementation layer.  The current production
  path is scrapping_module/social.py, which adds httpx-based strategies (Google
  SERP for LinkedIn; unofficial API and embedded JSON for Instagram) on top of
  the Playwright fallback, making it faster and more resilient.

  The engines here may still be wired in for direct Playwright scraping scenarios
  or serve as reference implementations for the DOM-querying logic.
"""
