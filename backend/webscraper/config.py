"""Root-level scraper configuration.

This module provides all tunable parameters for the low-level scraping engine.
It is imported directly by scraper.py, scrapping_module/social.py, and
scrapping_module/stealth.py — before the FastAPI app or Pydantic settings are
loaded — so it must be a plain Python module with no heavy dependencies.

Every value has a hard-coded default that works out of the box.  Any value can
be overridden at runtime via environment variables or a .env file at the project
root (loaded via python-dotenv if installed).  This pattern lets developers tune
the scraper for different environments (CI, Docker, local) without code changes.

Relationship to app/config/settings.py:
  app/config/settings.py is the *canonical* Pydantic-Settings config for the
  FastAPI layer (database URLs, API keys, LLM settings, etc.).  This file only
  covers the scraping engine parameters consumed below the API layer.
"""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass  # dotenv is optional; env vars still work without it


# ---------------------------------------------------------------------------
# Typed env-var helpers
# ---------------------------------------------------------------------------

def _int(key: str, default: int) -> int:
    """Read an integer from the environment, falling back to default."""
    return int(os.getenv(key, default))


def _float(key: str, default: float) -> float:
    """Read a float from the environment, falling back to default."""
    return float(os.getenv(key, default))


def _bool(key: str, default: bool) -> bool:
    """Read a boolean from the environment.

    Truthy string values: "1", "true", "yes", "on" (case-insensitive).
    Any other value (including absence of the variable) uses the default.
    """
    val = os.getenv(key)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Concurrency & Timing
# ---------------------------------------------------------------------------

# Maximum simultaneous in-flight HTTP requests across all domains.
# Lower values are more polite; higher values are faster (more aggressive).
MAX_CONCURRENT_REQUESTS: int = _int("MAX_CONCURRENT_REQUESTS", 5)

# Per-request timeout in seconds for both httpx and Playwright HTTP requests.
REQUEST_TIMEOUT: int = _int("REQUEST_TIMEOUT", 30)   # seconds

# How many times to retry a failed request before giving up.
RETRY_TIMES: int = _int("RETRY_TIMES", 3)

# HTTP status codes that warrant a retry (server-side transient failures).
# 429 = Too Many Requests, 408 = Request Timeout.
RETRY_HTTP_CODES: list[int] = [500, 502, 503, 504, 408, 429]

# Minimum wait between requests to the same domain (seconds).
# Prevents rate-limiting and reduces server load.
MIN_DELAY: float = _float("MIN_DELAY", 1.0)

# Upper bound on the adaptive per-domain delay (seconds).
MAX_DELAY: float = _float("MAX_DELAY", 5.0)

# Adaptive throttle target: controls how delay scales with latency.
# delay = latency / TARGET_CONCURRENCY — at concurrency=2, a 2-second
# response sets the delay to 1 second between requests.
AUTOTHROTTLE_TARGET_CONCURRENCY: float = _float("AUTOTHROTTLE_TARGET_CONCURRENCY", 2.0)


# ---------------------------------------------------------------------------
# JS Rendering (Playwright)
# ---------------------------------------------------------------------------

# Maximum time Playwright waits for a page to load, in milliseconds.
# Higher than REQUEST_TIMEOUT because JS-heavy pages take longer to render.
JS_RENDER_TIMEOUT: int = _int("JS_RENDER_TIMEOUT", 30_000)   # ms

# Run the browser in headless mode (no visible window).  Set to False for
# debugging (shows the browser UI so you can watch the scrape live).
BROWSER_HEADLESS: bool = _bool("BROWSER_HEADLESS", True)

# Which browser engine Playwright uses.  Chromium is the default because it
# has the best compatibility and the smallest footprint.
BROWSER_TYPE: str = os.getenv("BROWSER_TYPE", "chromium")    # chromium | firefox | webkit


# ---------------------------------------------------------------------------
# User-Agent Pool — realistic browser strings used for HTTP rotation
# ---------------------------------------------------------------------------
# Each request picks a random UA from this list so requests look like they
# come from different browsers/devices rather than a single automated client.
USER_AGENTS: list[str] = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome on iPhone — included so some requests appear to come from mobile.
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    # Firefox on Windows — provides browser diversity; some sites treat Firefox differently.
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


# ---------------------------------------------------------------------------
# Default browser-like request headers
# ---------------------------------------------------------------------------
# These headers accompany every httpx request.  Together they mimic the HTTP
# request that Chrome sends when navigating to a page, making the traffic
# look like a real browser session to basic bot-detection heuristics.
DEFAULT_HEADERS: dict[str, str] = {
    # Wide Accept tells the server we can handle any content type.
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    # Sec-Fetch-* headers are set by real browsers to describe the request context.
    # Their presence (and correct values) is checked by some WAFs/CDNs.
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}
