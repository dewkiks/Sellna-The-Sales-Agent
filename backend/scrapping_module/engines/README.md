# scrapping_module/engines — Platform Engine Class Hierarchy

This sub-package defines the abstract `SocialEngine` base class and the original Playwright-only concrete implementations for LinkedIn and Instagram.  The class hierarchy establishes a clean interface contract: any platform engine must implement `identify(url)` (so a dispatcher can select the right engine for a given URL) and `scrape(page, url)` (to perform the actual extraction using a provided Playwright page).  A shared `auto_scroll` utility on the base class handles lazy-loaded content without duplicating the scroll logic across engines.

## Files

| File | Description |
|------|-------------|
| `__init__.py` | Package initialiser; explains the sub-package role and the relationship to `social.py`. |
| `base.py` | `SocialEngine` abstract base class — defines `identify()`, `scrape()`, and the shared `auto_scroll()` utility. |
| `instagram.py` | `InstagramEngine` — uses Playwright CSS selectors to extract username, bio, and stats from Instagram's rendered profile DOM. |
| `linkedin.py` | `LinkedInEngine` — uses Playwright CSS selectors to extract name, headline, location, about, and experience from LinkedIn's public profile DOM. |

## How It Fits the Architecture

```
scrapping_module/social.py  (production path)
    └── _scrape_instagram_browser()
            └── Uses sync_playwright directly (not these engine classes)

scrapping_module/engines/   (engine class hierarchy)
    SocialEngine  (base.py)  ← abstract interface
        ├── LinkedInEngine   (linkedin.py)   ← Playwright DOM scraping
        └── InstagramEngine  (instagram.py)  ← Playwright DOM scraping
```

The engines in this sub-package are the **earlier Playwright-only** implementations.  The current production path lives in `social.py`, which adds cheaper httpx-based strategies on top, calling these Playwright engines only as a final fallback (and even then uses `sync_playwright` with network interception directly rather than the DOM-selector engines).  These classes are retained as a clean reference implementation and may be wired back in for simpler deployment scenarios.

## Likely Exam Questions

**Q: What is the purpose of the abstract base class `SocialEngine`?**
A: It defines the interface contract that every platform engine must satisfy: `identify(url)` returns True if the engine handles that platform, and `scrape(page, url)` performs the extraction. This allows a dispatcher to iterate over all registered engines and delegate to the correct one without knowing anything about specific platforms. It also provides the shared `auto_scroll` utility so subclasses don't duplicate scrolling logic.

**Q: Why does `SocialEngine` use Python's `ABC` (Abstract Base Class)?**
A: Using `ABC` and `@abstractmethod` enforces at class-definition time that every subclass implements both `identify` and `scrape`. If a developer forgets to implement one, Python raises a `TypeError` when the class is instantiated — catching the bug early rather than at runtime when the method is called.

**Q: How does `LinkedInEngine` handle the LinkedIn authentication wall?**
A: It uses CSS selectors targeting LinkedIn's "public" guest-visible profile layout (`h1.top-card-layout__title`, `h2.top-card-layout__headline`, etc.). If LinkedIn redirects to the login page, these selectors return empty strings. This is a known limitation; the production `social.py` avoids it entirely by reading LinkedIn data from Google's search index instead.

**Q: How does `InstagramEngine` detect whether a URL is a profile page or a post page?**
A: It checks whether `/p/` appears in the URL. Post URLs follow the pattern `instagram.com/p/<shortcode>/`; all other Instagram URLs are treated as profile pages. Profile pages extract username, bio, and stats; post pages extract the caption from the `<h1>` element.

**Q: What does `auto_scroll` do and why is the delay randomised?**
A: `auto_scroll` calls `window.scrollTo(0, document.body.scrollHeight)` in a loop to trigger infinite-scroll content loading. The delay between scrolls is randomised between 1.5 and 2.0 seconds to avoid a perfectly uniform scroll pattern, which some bot-detection systems flag as automated behaviour (real users scroll at irregular intervals).

**Q: Why do the Playwright strategies use `wait_until="networkidle"` instead of `"load"` or `"domcontentloaded"`?**
A: Social-media platforms are single-page applications that render content by making additional API/XHR calls after the initial HTML loads. `"load"` fires too early (before JavaScript has run and made those calls). `"networkidle"` waits until there are no more than 2 in-flight network requests for 500 ms, which is a reliable signal that all dynamic content has been fetched and rendered.
