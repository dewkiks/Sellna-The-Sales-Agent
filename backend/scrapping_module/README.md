# scrapping_module — Social-Media Scraping Subsystem

This package contains all social-media scraping logic for Sellna.ai.  Given a LinkedIn or Instagram profile URL, it retrieves structured profile data (name, headline, bio, follower counts, recent posts) using a layered multi-strategy approach that starts with lightweight HTTP requests and escalates to a full headless browser only when necessary.  The package is consumed by `app/services/scraping_service.py`, which is called by the pipeline's **SocialAgent** to enrich competitor and persona profiles with social-media intelligence.

## Files

| File | Description |
|------|-------------|
| `__init__.py` | Package initialiser; documents the package purpose and structure. |
| `social.py` | Production scraper: `SocialScraper` class + all LinkedIn and Instagram strategies (Google SERP bypass, unofficial API, embedded JSON extraction, Playwright browser intercept). |
| `stealth.py` | Playwright fingerprint-masking utility (`apply_stealth`); patches `navigator.webdriver` and other bot-detection markers before page navigation. |
| `engines/` | Sub-package containing the abstract `SocialEngine` base class and the older Playwright-only `LinkedInEngine` / `InstagramEngine` implementations. |

## How It Fits the Architecture

```
SocialAgent (app/agents/*)
    │
    └── app/services/scraping_service.py
            │
            └── scrapping_module/social.py  ← SocialScraper.scrape_batch()
                    │
                    ├── LinkedIn → _scrape_linkedin_via_google()   [httpx → Google SERP]
                    │               └── Google Cache fallback       [httpx → webcache]
                    │
                    └── Instagram → _scrape_instagram_sync()
                            ├── Strategy 1: _scrape_instagram_api()          [httpx]
                            ├── Strategy 2: _scrape_instagram_json_embed()   [httpx]
                            └── Strategy 3: _scrape_instagram_browser()      [Playwright in thread]
```

`scrape_batch()` is an async method; it wraps the synchronous scraping functions using `asyncio.run_in_executor` so the FastAPI event loop is never blocked while scraping is in progress.

## Likely Exam Questions

**Q: Why not scrape LinkedIn directly with a browser?**
A: LinkedIn requires authentication for most profile content and blocks headless browsers aggressively (returning HTTP 999 or the login wall). Instead, we scrape Google's search index, which contains LinkedIn profile summaries (name, headline, about) without requiring authentication. This sidesteps both the auth wall and the bot detection.

**Q: How are LinkedIn profiles discovered without the LinkedIn API?**
A: We search Google for the exact LinkedIn profile URL (`site:linkedin.com/in/<username>`) using httpx with browser-like headers. Google's SERP result card contains the profile name (from `<h3>`), job title (parsed from the LinkedIn title format "Name - Title | LinkedIn"), and a snippet of the "about" text. As a fallback, we fetch Google's cached copy of the LinkedIn page and read its `og:title` / `og:description` meta tags.

**Q: Why does `scrape_batch` use a `ThreadPoolExecutor` instead of `asyncio`?**
A: The Instagram browser strategy uses Playwright's synchronous API (`sync_playwright`). On Windows, the asyncio event loop running uvicorn cannot spawn the subprocess Playwright needs. Running it inside a thread sidesteps this OS-level restriction while keeping the public `scrape_batch` interface fully async via `run_in_executor`.

**Q: How does the multi-strategy cascade for Instagram work?**
A: Three strategies are tried in order — (1) Instagram's unofficial `web_profile_info` API endpoint (fastest, one HTTP call after cookie grab), (2) regex extraction of embedded JSON blobs from the page source (medium), (3) a full Playwright browser session that intercepts every network response the page makes and captures the GQL/API JSON payloads in memory. The first strategy to return a valid username wins.

**Q: What is the difference between this package and `scraper.py` in the project root?**
A: `scraper.py` is a general-purpose web scraper that fetches any URL and returns raw HTML; it is used by the WebAgent to scrape competitor websites. `scrapping_module` is platform-specific: it knows about LinkedIn and Instagram's DOM structures, APIs, and anti-bot measures, and it returns structured profile data (not raw HTML). They are separate subsystems called by different agents.

**Q: How does stealth.py reduce bot detection?**
A: `apply_stealth()` calls `playwright-stealth`'s library (which patches dozens of browser fingerprinting properties) and then adds a manual `Object.defineProperty` script that sets `navigator.webdriver` to `undefined`. These patches run as init scripts before any page content loads, so anti-bot checks that execute at page startup see values consistent with a real Chrome browser.

**Q: What does `_parse_ig_user_data` do and why is it needed?**
A: Instagram has changed its API response format multiple times (old edge-based format vs. new flat format for follower counts, post edges vs. items arrays, etc.). `_parse_ig_user_data` centralises the normalisation logic so all three Instagram strategies can share a single parser that handles every known format variation and always produces a consistent output dict.
