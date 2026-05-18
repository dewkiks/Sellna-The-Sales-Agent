"""InstagramEngine — Playwright-based scraper for Instagram profile and post pages.

This engine uses CSS selectors against the rendered Instagram DOM to extract
profile data.  It is part of the engines/ class hierarchy (SocialEngine base).

Limitations:
  Instagram frequently changes its DOM structure, which makes CSS-selector-based
  scraping brittle.  The current production path (social.py) supplements this
  with API interception (Strategy 3: browser + network intercept) which is more
  robust because it reads structured JSON from Instagram's internal API responses
  rather than parsing the rendered HTML.

  This engine is retained as a reference implementation and for cases where the
  DOM structure is stable enough for selector-based extraction to work.
"""

from .base import SocialEngine
from playwright.async_api import Page
import json


class InstagramEngine(SocialEngine):
    """Playwright DOM scraper for Instagram profiles and individual posts."""

    def identify(self, url: str) -> bool:
        """Return True for any URL on the instagram.com domain."""
        return "instagram.com" in url

    async def scrape(self, page: Page, url: str) -> dict:
        """Navigate to an Instagram URL and extract profile or post data via DOM selectors.

        Behaviour differs based on URL type:
          - Profile page (default): extracts username, bio, and follower stats
            using CSS selectors against Instagram's rendered DOM.
          - Post page (/p/ URLs): extracts the post caption from the <h1> element.

        Note: Instagram's DOM is heavily JavaScript-driven.  The page must have
        fully loaded (wait_until="networkidle") before selectors are evaluated.
        Stats (followers, following, posts count) are read from the <ul><li><span>
        list that Instagram renders in the profile header.

        Args:
            page: Playwright Page object (stealth patches already applied by caller).
            url:  Instagram profile or post URL.

        Returns:
            Dict with keys: platform, url, username, bio, followers, following,
            posts_count, posts, type.  Includes "error" key on exception.
        """
        # wait_until="networkidle" waits until all XHR/fetch requests have settled,
        # ensuring the JavaScript-rendered profile content is fully present in the DOM.
        await page.goto(url, wait_until="networkidle", timeout=60000)

        data = {
            "platform": "Instagram",
            "url": url,
            "username": "",
            "bio": "",
            "followers": 0,
            "following": 0,
            "posts_count": 0,
            "posts": []
        }

        try:
            # Instagram often embeds data in JSON-LD or shared state.
            # Try to find the username first.
            if "/p/" in url:
                # Post page: Instagram displays the caption in an <h1>.
                data["type"] = "post"
                data["caption"] = await page.inner_text("h1") if await page.query_selector("h1") else ""
            else:
                # Profile page.
                data["type"] = "profile"

                # Username is rendered in the first <h2> on a profile page.
                h2 = await page.query_selector("h2")
                if h2:
                    data["username"] = await h2.inner_text()

                # Bio text is the last visible <span> inside the header section.
                bio_sel = "section main header section div span"
                bios = await page.query_selector_all(bio_sel)
                if bios:
                    # The last matching span is the bio, not a label or header.
                    data["bio"] = await bios[-1].inner_text()

                # Follower / following / post count stats appear in an ordered list.
                # Instagram renders them as: [posts, followers, following] in <li><span>.
                stats = await page.query_selector_all("ul li span")
                if len(stats) >= 3:
                    try:
                        # Some spans use a title= attribute for the full numeric value
                        # (e.g., "1,234,567") when the display is abbreviated ("1.2M").
                        data["posts_count"] = await stats[0].get_attribute("title") or await stats[0].inner_text()
                        data["followers"] = await stats[1].get_attribute("title") or await stats[1].inner_text()
                        data["following"] = await stats[2].inner_text()
                    except (IndexError, AttributeError):
                        pass  # Stats may be absent for private or restricted accounts.

        except Exception as e:
            data["error"] = str(e)

        return data
