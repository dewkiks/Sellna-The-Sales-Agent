"""Abstract base class defining the interface for all social-media scraping engines.

Every platform engine (LinkedIn, Instagram) inherits from SocialEngine and must
implement two abstract methods:
  - identify(url) — tells the dispatcher whether this engine handles the given URL.
  - scrape(page, url) — performs the actual scraping using the provided Playwright page.

The base class also provides a shared utility (auto_scroll) that all engines can
reuse to trigger lazy-loaded content (infinite-scroll feeds, deferred images, etc.).

Class hierarchy:
  SocialEngine  (abstract, this file)
    ├── LinkedInEngine  (engines/linkedin.py)
    └── InstagramEngine (engines/instagram.py)
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from playwright.async_api import Page
import asyncio
import random


class SocialEngine(ABC):
    """Abstract interface for a platform-specific Playwright scraping engine.

    To add support for a new social platform, subclass SocialEngine and
    implement identify() and scrape().  The dispatcher in the calling code
    iterates over registered engines and delegates to the first one whose
    identify() returns True for the given URL.
    """

    @abstractmethod
    def identify(self, url: str) -> bool:
        """Return True if this engine is capable of scraping the given URL.

        Used by the dispatcher to select the correct engine without inspecting
        platform-specific URL patterns in the calling code.

        Args:
            url: The social-media profile or post URL to test.

        Returns:
            True if this engine should handle the URL, False otherwise.
        """
        return False

    @abstractmethod
    async def scrape(self, page: Page, url: str) -> dict:
        """Navigate to url using the provided Playwright page and extract profile data.

        The caller is responsible for creating the Page (with any stealth patches
        already applied) and closing it after this method returns.

        Args:
            page: A ready Playwright Page object pointing at a blank tab.
            url:  The social-media URL to scrape.

        Returns:
            Dict containing extracted profile data.  Keys vary by platform;
            see the concrete subclass for the exact schema.
            Should include an "error" key on failure.
        """
        return {}

    async def auto_scroll(self, page: Page, max_scrolls: int = 5) -> None:
        """Scroll to the bottom of the page repeatedly to trigger lazy loading.

        Social-media feeds and image grids often use "infinite scroll" — content
        is loaded asynchronously as the user scrolls.  This method simulates that
        by scrolling to document.body.scrollHeight in a loop, waiting between
        each scroll to allow the network requests to complete and new content to
        render before the next scroll.

        Args:
            page:        The Playwright Page to scroll.
            max_scrolls: Maximum number of scroll actions to perform.
                         Each scroll is followed by a 1.5–2 second pause.
        """
        for _ in range(max_scrolls):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            # Random delay between 1.5 and 2.0 seconds — avoids a perfectly
            # uniform scroll pattern that some bot-detection systems flag.
            await asyncio.sleep(1.5 + (0.5 * random.random()))
