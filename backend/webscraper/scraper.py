"""Core async web scraping engine for the Sellna.ai pipeline.

This module is the low-level fetching workhorse used by the pipeline's
WebAgent (via scraper_standalone.py) to retrieve competitor websites.

Fetch strategy (adaptive, per-URL):
  1. httpx (lightweight, fast, no browser overhead) — used first for all URLs.
  2. Playwright (headless Chromium/Firefox/WebKit) — used automatically as a
     fallback whenever httpx is blocked (HTTP 401/403/406/429/503/999).
     render_js=True forces Playwright for every request.

Anti-detection techniques applied:
  - Random User-Agent rotation from a curated realistic pool (config.py).
  - Browser-like headers (Accept, Sec-Fetch-*, Upgrade-Insecure-Requests)
    to mimic a real browser HTTP session.
  - Per-domain adaptive throttling: delays are computed from observed
    response latency so the scraper self-limits under server pressure.
  - stealth.py patches applied to every Playwright page (removes
    navigator.webdriver and other bot-detection markers).
  - URL deduplication (SHA-1 fingerprint) to avoid re-fetching the same
    resource within a session.

Key classes / entry points:
  ScrapeResult  — plain dataclass holding the outcome of one fetch.
  Scraper       — main class; call scrape_urls([...]) to fetch a batch.
"""

from __future__ import annotations

import asyncio
import hashlib
import random
import re
import time
import traceback
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright

from webscraper import config
from scrapping_module.stealth import apply_stealth

# Once a headless-browser launch fails (Playwright not installed, or asyncio
# subprocesses unsupported — e.g. under uvicorn on Windows), skip all further
# JS-render attempts this process instead of retrying and spamming tracebacks.
_JS_DISABLED = False


@dataclass
class ScrapeResult:
    """Result container for a single URL fetch attempt.

    Attributes:
        url:            Final URL after any redirects.
        status:         HTTP status code (0 if connection-level failure).
        success:        True when status is 2xx–3xx and HTML was retrieved.
        html:           Decoded response body (empty on failure).
        error:          Human-readable error message (empty on success).
        redirect_chain: Ordered list of intermediate URLs followed.
        elapsed_ms:     Total request round-trip time in milliseconds.
        rendered:       True when Playwright was used (JS was executed).
    """
    url: str
    status: int = 0
    success: bool = False
    html: str = ""
    error: str = ""
    redirect_chain: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0
    rendered: bool = False


class Scraper:
    """Async scraper with adaptive throttling, retry, UA rotation, and JS rendering support.

    Usage:
        scraper = Scraper(render_js=False)
        results = await scraper.scrape_urls(["https://example.com"])

    Args:
        proxy:      Optional proxy URL forwarded to both httpx and Playwright.
        render_js:  If True, always use Playwright instead of httpx.
                    If False (default), httpx is tried first; Playwright is
                    used automatically on bot-block responses.
    """

    def __init__(self, proxy: str | None = None, render_js: bool = False):
        self.proxy = proxy
        self.render_js = render_js
        self.delays: dict[str, float] = {}  # per-domain adaptive delay (seconds)
        self.seen: set[str] = set()          # SHA-1 fingerprints of already-queued URLs
        # Semaphore caps simultaneous in-flight requests to avoid overwhelming targets.
        self.semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_REQUESTS)
        self._client: httpx.AsyncClient | None = None
        self._playwright = None
        self._browser = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Return a shared httpx.AsyncClient, creating it on first call.

        The client is reused across requests in a scrape batch for connection
        pooling (keep-alive). http2 is disabled to avoid a NotImplementedError
        on certain Windows event-loop / uvicorn configurations.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=dict(config.DEFAULT_HEADERS),
                timeout=httpx.Timeout(config.REQUEST_TIMEOUT),
                follow_redirects=True,
                http2=False,  # Disabled to avoid NotImplementedError on some Windows setups
                proxy=self.proxy,
            )
        return self._client

    async def _get_browser(self):
        """Return a shared Playwright browser instance, launching it on first call.

        Browser type (chromium / firefox / webkit) and headless mode are
        controlled by config.py so they can be changed via environment variables
        without code changes.
        """
        if self._playwright is None:
            pw = await async_playwright().start()
            self._playwright = pw
            launch_options = {"headless": config.BROWSER_HEADLESS}
            if config.BROWSER_TYPE == "chromium":
                self._browser = await pw.chromium.launch(**launch_options)
            elif config.BROWSER_TYPE == "firefox":
                self._browser = await pw.firefox.launch(**launch_options)
            else:
                self._browser = await pw.webkit.launch(**launch_options)
        return self._browser

    async def close(self) -> None:
        """Release all held resources: httpx client, Playwright browser and context."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def scrape_urls(self, urls: list[str]) -> list[ScrapeResult]:
        """Scrape a batch of URLs concurrently with deduplication.

        Duplicate URLs (same scheme + host + path, query params sorted) are
        silently dropped before fetching so the same page is never hit twice
        in one session.

        Args:
            urls: List of absolute URLs to fetch.

        Returns:
            List of ScrapeResult objects, one per unique input URL, in order.
        """
        unique_urls: list[str] = []
        for url in urls:
            fp = self._fingerprint(url)
            if fp not in self.seen:
                self.seen.add(fp)
                unique_urls.append(url)

        # Launch all fetches concurrently; the semaphore inside each fetch
        # caps the actual number of simultaneous open connections.
        tasks = [self._fetch_with_retry(url) for url in unique_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        out: list[ScrapeResult] = []
        for url, result in zip(unique_urls, results):
            if isinstance(result, Exception):
                out.append(ScrapeResult(url=url, error=str(result)))
            elif isinstance(result, ScrapeResult):
                out.append(result)
            else:
                out.append(ScrapeResult(url=url, error="Unknown result type"))

        await self.close()
        return out

    # ------------------------------------------------------------------
    # Fetching
    # ------------------------------------------------------------------

    async def _fetch_with_retry(self, url: str) -> ScrapeResult:
        """Fetch a single URL, retrying with exponential backoff on failure.

        Retry logic:
          - Retries are attempted only for codes listed in config.RETRY_HTTP_CODES
            (network errors / server-side transient failures like 500, 502, 503).
          - Backoff formula: 2^attempt + random(0, 1) seconds — prevents
            thundering-herd when many requests hit the same domain at once.
          - After config.RETRY_TIMES retries, the last error is returned.

        Auto-fallback to Playwright:
          When render_js=False (httpx mode) and the server responds with a
          bot-block code (401, 403, 406, 429, 503, 999), the method
          transparently retries the same URL with Playwright JS rendering.
          LinkedIn uses the non-standard 999 code for bot blocks.
        """
        last_error = ""
        retry_times = int(config.RETRY_TIMES)

        for attempt in range(1 + retry_times):
            try:
                if self.render_js:
                    result = await self._fetch_js(url)
                else:
                    result = await self._fetch_static(url)

                    # Auto-fallback to JS if blocked.
                    # 999 = LinkedIn's custom bot-block code.
                    # 403 = Forbidden, 401 = Unauthorized, 429 = Rate limited, 406 = Not Acceptable.
                    BLOCK_CODES = {401, 403, 406, 429, 503, 999}
                    if not result.success and result.status in BLOCK_CODES:
                        result = await self._fetch_js(url)

                if result.success:
                    return result

                # Only retry on transient server-side codes, not permanent errors.
                if result.status in config.RETRY_HTTP_CODES and attempt < retry_times:
                    last_error = f"HTTP {result.status}"
                    # Exponential backoff with jitter to avoid synchronized retries.
                    backoff = (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(backoff)
                    continue
                return result
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < retry_times:
                    backoff = (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(backoff)
                    continue

        return ScrapeResult(url=url, error=last_error)

    async def _fetch_static(self, url: str) -> ScrapeResult:
        """Fetch a URL using httpx (no browser, no JavaScript execution).

        httpx is the fast path: it sends a plain HTTP request and returns
        the raw server HTML. Works for static sites and server-rendered pages.
        It will fail (and trigger JS fallback) on single-page apps that need
        JavaScript to render their content, or sites that actively block
        non-browser traffic (LinkedIn, Instagram).

        Throttling: waits for the domain's current adaptive delay plus a random
        0–50% jitter before sending the request, to mimic human browsing pace.
        """
        domain = urlparse(url).netloc
        delay = float(self._get_delay(domain))
        # Jitter prevents the scraper from hitting the same domain at a perfectly
        # regular interval, which is a common bot-detection signal.
        await asyncio.sleep(delay + (delay * random.uniform(0, 0.5)))

        client = await self._get_client()
        # Rotate User-Agent per request so different requests look like different browsers.
        ua = random.choice(config.USER_AGENTS)
        headers = {"User-Agent": ua}

        async with self.semaphore:  # Cap concurrency across all in-flight requests.
            start = time.perf_counter()
            response = await client.get(url, headers=headers)
            elapsed = float((time.perf_counter() - start) * 1000)

        self._adjust_delay(domain, float(elapsed / 1000), response.status_code)

        success = 200 <= response.status_code < 400
        html = self._decode_response(response) if success else ""
        return ScrapeResult(
            url=str(response.url),  # May differ from input if redirects occurred.
            status=response.status_code,
            success=success,
            html=html,
            error="" if success else f"HTTP {response.status_code}",
            redirect_chain=[str(r.url) for r in response.history],
            elapsed_ms=round(elapsed, 1),
            rendered=False  # httpx never executes JavaScript.
        )

    async def _fetch_js(self, url: str) -> ScrapeResult:
        """Fetch a URL using a headless browser via Playwright (JavaScript executed).

        Playwright is used when:
          a) render_js=True was set on the Scraper instance, OR
          b) httpx received a bot-block status code (auto-fallback in _fetch_with_retry).

        A fresh browser context (isolated cookies, storage) is created per
        request and destroyed in the finally block, so pages cannot share state.

        Stealth patches (apply_stealth) are applied to every new page before
        navigation to mask Playwright's automation markers.

        The process-level _JS_DISABLED flag prevents repeated failure noise:
        if the browser cannot be launched (Playwright binaries missing, or
        asyncio subprocess limitation under uvicorn on Windows), all subsequent
        JS-render attempts skip immediately instead of re-raising.
        """
        global _JS_DISABLED
        if _JS_DISABLED:
            return ScrapeResult(
                url=url,
                error="JS rendering disabled — headless browser unavailable in this environment",
            )

        domain = urlparse(url).netloc
        delay = float(self._get_delay(domain))
        await asyncio.sleep(delay + (delay * random.uniform(0, 0.5)))

        try:
            browser = await self._get_browser()
        except Exception as exc:
            # Browser can't launch here (Playwright browsers not installed, or
            # asyncio subprocesses unsupported under uvicorn on Windows). Disable
            # JS for the rest of the process so we don't retry and spam errors.
            _JS_DISABLED = True
            return ScrapeResult(
                url=url, error=f"JS rendering unavailable: {type(exc).__name__}"
            )
        if not browser:
            return ScrapeResult(url=url, error="Browser not initialized")

        ua = random.choice(config.USER_AGENTS)

        async with self.semaphore:
            start = time.perf_counter()
            # Isolated context per request: no cookies or auth bleed between pages.
            context = await browser.new_context(user_agent=ua)
            page = await context.new_page()
            # Apply browser-fingerprint masking before the page loads anything.
            await apply_stealth(page)
            try:
                # wait_until="networkidle" means Playwright waits until there are
                # no more than 2 in-flight network requests for 500 ms — a good
                # heuristic for "the page has fully rendered".
                response = await page.goto(url, wait_until="networkidle", timeout=config.JS_RENDER_TIMEOUT)
                elapsed = float((time.perf_counter() - start) * 1000)
                status = response.status if response else 0
                # page.content() returns the *post-JavaScript* DOM, unlike httpx
                # which returns the raw server HTML.
                html = await page.content()
                success = 200 <= status < 400

                self._adjust_delay(domain, float(elapsed / 1000), status)

                return ScrapeResult(
                    url=url,
                    status=status,
                    success=success,
                    html=html,
                    error="" if success else f"HTTP {status}",
                    elapsed_ms=round(elapsed, 1),
                    rendered=True  # JavaScript was executed.
                )
            except Exception as e:
                return ScrapeResult(url=url, error=str(e), rendered=True)
            finally:
                # Always close the context to free browser memory and cookies.
                await context.close()

    # ------------------------------------------------------------------
    # Adaptive Throttle
    # ------------------------------------------------------------------

    def _get_delay(self, domain: str) -> float:
        """Return the current inter-request delay for a domain (seconds).

        Starts at config.MIN_DELAY and increases automatically as the server
        responds slowly or with error codes.
        """
        return self.delays.get(domain, config.MIN_DELAY)

    def _adjust_delay(self, domain: str, latency: float, status: int) -> None:
        """Update the adaptive delay for a domain based on observed latency.

        Algorithm (inspired by Scrapy's AutoThrottle):
          target_delay = latency / AUTOTHROTTLE_TARGET_CONCURRENCY
          new_delay    = avg(current, target)   — gradual smoothing
          new_delay    = clamp(new_delay, MIN_DELAY, MAX_DELAY)

        Error responses (status >= 400) never decrease the delay, so the
        scraper automatically backs off when under server pressure.

        Args:
            domain:  Hostname whose delay to adjust.
            latency: Observed round-trip time in seconds.
            status:  HTTP status code of the response.
        """
        target_delay = latency / config.AUTOTHROTTLE_TARGET_CONCURRENCY
        current = self.delays.get(domain, config.MIN_DELAY)
        # Smooth toward the target to avoid sudden large swings.
        new_delay = max(target_delay, (current + target_delay) / 2.0)
        new_delay = max(config.MIN_DELAY, min(new_delay, config.MAX_DELAY))
        # On error: only update if the new delay would be higher (i.e., backing off).
        if status >= 400 and new_delay <= current:
            return
        self.delays[domain] = new_delay

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_response(response: httpx.Response) -> str:
        """Decode an httpx response body to a Python string.

        Encoding resolution order (robust against misconfigured servers):
          1. Use the charset declared in the Content-Type header if present.
          2. Search the first 4 KB of raw bytes for an HTML <meta charset> tag.
          3. Try common encodings in order: utf-8, latin-1, cp1252.
          4. UTF-8 with replacement characters (never raises).

        Args:
            response: A completed httpx.Response object.

        Returns:
            Decoded HTML as a str.
        """
        content_type = response.headers.get("content-type", "")
        if "charset" in content_type.lower():
            # httpx already decoded it correctly using the declared charset.
            return response.text
        raw = response.content
        # Sniff the first 4 KB for a meta charset declaration in the HTML itself.
        head = raw[:4096]
        match = re.search(rb'charset=["\']?\s*([a-zA-Z0-9_-]+)', head, re.I)
        if match:
            charset = match.group(1).decode("ascii", errors="ignore")
            try: return raw.decode(charset)
            except: pass
        # Fallback chain for servers that omit charset declarations.
        for enc in ("utf-8", "latin-1", "cp1252"):
            try: return raw.decode(enc)
            except: continue
        # Last resort: utf-8 with replacement (U+FFFD) — always succeeds.
        return raw.decode("utf-8", errors="replace")

    @staticmethod
    def _fingerprint(url: str) -> str:
        """Produce a stable SHA-1 hash for a URL to detect duplicates.

        Normalization applied before hashing:
          - scheme and host are lowercased.
          - query parameters are sorted alphabetically so that
            ?b=2&a=1 and ?a=1&b=2 produce the same fingerprint.
          - Fragment (#anchor) is intentionally ignored because fragments are
            client-side only and do not change the server response.

        Args:
            url: Absolute URL string.

        Returns:
            40-character hex SHA-1 digest.
        """
        parsed = urlparse(url)
        normalized = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path}"
        if parsed.query:
            # Sort query params so ?a=1&b=2 and ?b=2&a=1 hash the same.
            normalized += "?" + "&".join(sorted(parsed.query.split("&")))
        return hashlib.sha1(normalized.encode()).hexdigest()
