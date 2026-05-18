"""Manual dev/verification script — smoke-tests the Scraper against a live URL.

This is NOT a production module and NOT part of the sales pipeline.
Run it directly (python verify_fix.py) after making changes to scraper.py
to confirm the fix works end-to-end against a real website.

What it checks:
  - Scraper can be instantiated without errors.
  - scrape_urls() returns a ScrapeResult with status/success/html populated.
  - The auto-fallback from httpx to Playwright (on bot-block responses) works,
    because the Calgary Zoo events page is known to require JavaScript.

Expected output on success:
    URL: https://www.calgaryzoo.com/events/penguin-walk/
    Status: 200
    Success: True
    Error:
    HTML Length: <non-zero integer>
"""

import asyncio
import sys
from pathlib import Path

# Add project root to sys.path so imports work when run from any directory.
sys.path.append(str(Path(__file__).resolve().parent.parent))

from webscraper.scraper import Scraper


async def test():
    print("Initializing Scraper...")
    # render_js=False: starts with httpx; will auto-fallback to Playwright if
    # the target returns a bot-block code (403/999/etc.).
    s = Scraper(render_js=False)
    print("Scraping Calgary Zoo...")
    res = await s.scrape_urls(["https://www.calgaryzoo.com/events/penguin-walk/"])
    for r in res:
        print(f"URL: {r.url}")
        print(f"Status: {r.status}")
        print(f"Success: {r.success}")
        print(f"Error: {r.error}")
        print(f"HTML Length: {len(r.html)}")
    await s.close()


if __name__ == "__main__":
    asyncio.run(test())
