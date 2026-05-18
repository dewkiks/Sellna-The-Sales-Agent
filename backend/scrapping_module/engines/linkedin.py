"""LinkedInEngine — Playwright-based scraper for LinkedIn public profile pages.

This engine navigates to a LinkedIn profile URL with a headless browser and
extracts data by querying the rendered DOM using CSS selectors.

Important limitation — authentication wall:
  LinkedIn redirects unauthenticated visitors to its login page for most
  profile content.  The CSS selectors used here (h1.top-card-layout__title,
  h2.top-card-layout__headline, etc.) target the "public" profile layout that
  LinkedIn renders for guest visitors and search-engine crawlers.  If LinkedIn
  detects the browser as a bot and shows the login wall instead, these selectors
  will return empty strings.

  The current production path (social.py — _scrape_linkedin_via_google) avoids
  this problem entirely by reading LinkedIn data indirectly from Google's search
  index instead of scraping LinkedIn directly.  This engine is the earlier
  implementation and serves as a fallback or reference.
"""

from .base import SocialEngine
from playwright.async_api import Page
import re


class LinkedInEngine(SocialEngine):
    """Playwright DOM scraper for LinkedIn public profile pages."""

    def identify(self, url: str) -> bool:
        """Return True for any URL on the linkedin.com domain."""
        return "linkedin.com" in url

    async def scrape(self, page: Page, url: str) -> dict:
        """Navigate to a LinkedIn profile and extract data via CSS selectors.

        Targets LinkedIn's "public" (guest-visible) profile layout.  The
        selectors correspond to the class names LinkedIn uses for the header
        card and experience section on non-authenticated profile views.

        Experience entries are extracted by iterating over all
        li.experience-item elements and reading the title (h3) and company (h4)
        from each one.

        Args:
            page: Playwright Page object (stealth patches already applied by caller).
            url:  LinkedIn profile URL (e.g. https://www.linkedin.com/in/username/).

        Returns:
            Dict with keys: platform, url, profile_name, headline, location,
            about, experience.  The "experience" key is a list of dicts, each
            with "title" and "company".  Includes "error" key on exception.
        """
        # wait_until="networkidle" ensures the profile content has finished rendering.
        await page.goto(url, wait_until="networkidle", timeout=60000)

        data = {
            "platform": "LinkedIn",
            "url": url,
            "profile_name": "",
            "headline": "",
            "location": "",
            "about": "",
            "experience": []
        }

        try:
            # --- Header card: name, headline, location ---
            # These selectors target LinkedIn's public profile "top card" layout.
            name_el = await page.query_selector("h1.top-card-layout__title")
            data["profile_name"] = await name_el.inner_text() if name_el else ""

            headline_el = await page.query_selector("h2.top-card-layout__headline")
            data["headline"] = await headline_el.inner_text() if headline_el else ""

            # Location appears in a sub-line item span inside the header card.
            loc_el = await page.query_selector("span.top-card__subline-item")
            data["location"] = await loc_el.inner_text() if loc_el else ""

            # --- About section ---
            # The summary section contains a <p> tag with the "about" text.
            about_sel = "section.summary p"
            about_el = await page.query_selector(about_sel)
            if about_el:
                data["about"] = await about_el.inner_text()

            # --- Experience list ---
            # Each job entry is an <li class="experience-item"> containing:
            #   h3.experience-item__title   — the job title
            #   h4.experience-item__subtitle — the company name
            exp_items = await page.query_selector_all("li.experience-item")
            experience_list = []
            for item in exp_items:
                title_el = await item.query_selector("h3.experience-item__title")
                title = await title_el.inner_text() if title_el else ""

                company_el = await item.query_selector("h4.experience-item__subtitle")
                company = await company_el.inner_text() if company_el else ""

                # Only include entries that have at least a job title.
                if title:
                    experience_list.append({"title": title.strip(), "company": company.strip()})
            data["experience"] = experience_list

        except Exception as e:
            data["error"] = str(e)

        return data
