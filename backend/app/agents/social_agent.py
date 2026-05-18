"""Social Intelligence Agent — pipeline stage 4 (parallel with WebAgent).

Crawls the website of a subject (the analyzed company or a discovered
competitor) to harvest publicly visible social signals and contact information.

What it extracts:
  - Social accounts  : LinkedIn /company/ and Instagram organization URLs
    found anywhere in the raw HTML (typically footers and nav bars).
  - People           : real team members — name, job title, LinkedIn /in/ URL —
    discovered via three strategies ranked by reliability:
      1. JSON-LD Person schema markup (most accurate, machine-readable)
      2. LinkedIn /in/ anchor links with associated name text
      3. Name-shaped headings inside team-card containers (team pages only)
  - Emails + phones  : ``mailto:`` links, ``tel:`` links, and email-shaped
    strings in the raw HTML, filtered through a blocklist of dummy addresses.

Why raw HTML?  The scrapping_module extractor strips footer and nav elements
for cleanliness — but social links and contact details live precisely there.
SocialAgent works on the unstripped HTML so nothing is lost.

Concurrency model: fetches are batched per stage (homepage first, then
team/about/contact pages in one batch) rather than one-URL-at-a-time to
balance latency and connection reuse.

Pipeline position: stage 4, parallel with WebAgent.  Not required by later
RAG stages — its output is persisted to the DB for the API to return but
does not feed GapAnalysisAgent.

Key dependencies:
  - scraper.Scraper — the project's HTTP/Playwright scraping module
  - bs4.BeautifulSoup — HTML parsing for people extraction
  - app.schemas.social — SubjectSocials, SocialProfileData, PersonContact
"""

from __future__ import annotations

import json
import re
import time
import uuid
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.core.logging import get_logger
from app.schemas.social import PersonContact, SocialProfileData, SubjectSocials
from webscraper.scraper import Scraper

logger = get_logger(__name__)

# URL path segments that identify a team / leadership / about page — these are
# where bare "team card" name-scanning is allowed (homepages have too much noise).
_TEAM_PATH_SEGMENTS = {
    "about",
    "about-us",
    "team",
    "our-team",
    "the-team",
    "meet-the-team",
    "leadership",
    "people",
    "who-we-are",
    "founders",
    "staff",
}

# All info pages worth fetching (team pages + contact pages).
_INFO_SEGMENTS = _TEAM_PATH_SEGMENTS | {
    "company",
    "contact",
    "contact-us",
    "get-in-touch",
}

# Caps so a single pipeline run stays bounded.
_MAX_INFO_PAGES = 5
_MAX_PEOPLE = 25
_MAX_EMAILS = 30

# LinkedIn company + Instagram handle URLs, anywhere in the HTML.
_SOCIAL_RE = re.compile(
    r"https?://(?:[\w-]+\.)?"
    r"(?:linkedin\.com/company/[\w%.\-]+|instagram\.com/[\w.\-]+)",
    re.I,
)
_HREF_RE = re.compile(r"""href\s*=\s*['"]([^'"<>\s]+)['"]""", re.I)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]{1,40}@[A-Za-z0-9.\-]{2,}\.[A-Za-z]{2,18}")
_MAILTO_RE = re.compile(r"mailto:([^\"'?>\s]+)", re.I)
_TEL_RE = re.compile(r"""href\s*=\s*['"]tel:([^'"]{5,40})['"]""", re.I)

# Anchor / heading text that matches the name shape but is not a person.
_NON_NAME_WORDS = {
    "team", "contact", "about", "our", "us", "more", "get", "started",
    "privacy", "policy", "terms", "sign", "read", "learn", "home", "sales",
    "support", "careers", "free", "demo", "pricing", "product", "company",
    "blog", "news", "the", "and", "view", "all", "meet", "join", "apply",
    "login", "resources", "solutions", "case", "study", "book", "request",
}
_NAME_TOKEN_RE = re.compile(r"^[A-Z][A-Za-z'’.\-]{1,}$")
_PERSON_CONTAINER_RE = re.compile(
    r"team|member|person|people|leader|staff|founder|employee",
    re.I,
)

_IG_RESERVED = {"p", "reel", "reels", "explore", "accounts", "directory", "about", "stories"}
_EMAIL_BAD_EXT = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".css",
    ".js", ".woff", ".woff2", ".ttf",
)
_EMAIL_BAD_DOMAIN = (
    "sentry", "example.com", "example.org", "domain.com", "email.com",
    "yourdomain", "wixpress", "schema.org", "googleapis",
)


def _ensure_scheme(url: str) -> str:
    """Prepend https:// to bare domains like 'example.com' before fetching."""
    if not url.lower().startswith(("http://", "https://")):
        return "https://" + url
    return url


def _norm(url: str) -> str:
    """Strip query string, fragment, and trailing slash for deduplication."""
    return url.split("?")[0].split("#")[0].rstrip("/")


def _classify(url: str) -> tuple[str, str] | None:
    """Return (platform, profile_type) for an org social URL, or None.

    Only LinkedIn /company/ pages and top-level Instagram handles qualify.
    Personal LinkedIn /in/ profiles and reserved Instagram paths (e.g.
    /explore/, /reel/) are excluded — they belong to people, not the org.

    Args:
        url: Normalized social URL to classify.

    Returns:
        (platform_name, "organization") tuple, or None if the URL is not
        a recognized org-level social account.
    """
    low = url.lower()
    if "linkedin.com/company/" in low:
        return ("LinkedIn", "organization")
    if "instagram.com/" in low:
        handle = urlparse(low).path.strip("/")
        # Reject paths with a slash (sub-pages) or reserved segments
        # like /explore/ and /accounts/ that are not brand handles.
        if not handle or "/" in handle or handle in _IG_RESERVED:
            return None
        return ("Instagram", "organization")
    return None


def _iter_jsonld(data):
    """Walk a JSON-LD blob yielding every dict (incl. @graph entries).

    JSON-LD on team pages often uses @graph to list multiple Person objects
    in a single <script> tag.  This generator recurses into @graph so callers
    can treat every item uniformly.

    Args:
        data: Parsed JSON value — may be a dict, list, or nested combination.

    Yields:
        Every dict found at any depth of the structure.
    """
    if isinstance(data, dict):
        yield data
        graph = data.get("@graph")
        if isinstance(graph, list):
            for g in graph:
                yield from _iter_jsonld(g)
    elif isinstance(data, list):
        for item in data:
            yield from _iter_jsonld(item)


def _looks_like_name(text: str) -> bool:
    """Heuristic: does this string look like a human name?

    Accepts 2–4 space-separated tokens where every token starts with a
    capital letter (allowing apostrophes, hyphens, periods for names like
    "O'Brien" or "Smith-Jones") and none of the tokens appear in the
    _NON_NAME_WORDS blocklist (which filters common UI label words like
    "Contact", "Learn", "Team").

    Args:
        text: Candidate string to test.

    Returns:
        True if the string matches the name heuristic, False otherwise.
    """
    text = " ".join((text or "").split())
    if not (4 <= len(text) <= 50):
        return False
    tokens = text.split()
    if not (2 <= len(tokens) <= 4):
        return False
    for tok in tokens:
        if tok.lower() in _NON_NAME_WORDS or not _NAME_TOKEN_RE.match(tok):
            return False
    return True


def _extract_emails(html: str) -> set[str]:
    """Extract real email addresses from raw HTML.

    Two sources are combined:
      - _EMAIL_RE: catches email-shaped text anywhere in the page
      - _MAILTO_RE: catches addresses in href="mailto:..." links, which are
        more reliable because they are explicitly machine-readable

    Then a blocklist of bad extensions and dummy domains removes:
      - Image/font filenames that contain "@" (e.g. "icon@2x.png")
      - Placeholder domains used in templates ("example.com", "yourdomain")
      - Tracking/analytics domains ("sentry", "googleapis")

    Args:
        html: Raw HTML string for one page.

    Returns:
        Set of valid-looking email strings.
    """
    candidates = set(_EMAIL_RE.findall(html))
    for raw in _MAILTO_RE.findall(html):
        raw = raw.split("?")[0].strip()  # drop ?subject= query params
        if "@" in raw and " " not in raw:
            candidates.add(raw)
    out: set[str] = set()
    for email in candidates:
        low = email.lower()
        # Image filenames like "logo@2x.png" match the email regex — reject them.
        if low.endswith(_EMAIL_BAD_EXT) or "@2x" in low or "@3x" in low:
            continue
        domain = low.split("@")[-1]
        if any(bad in domain for bad in _EMAIL_BAD_DOMAIN):
            continue
        if len(email) > 100 or len(low.split("@")[0]) > 40:
            continue
        out.add(email)
    return out


def _extract_phones(html: str) -> set[str]:
    """Extract phone numbers from tel: href links in raw HTML.

    Only accepts numbers with 7–15 digits after stripping non-digit chars,
    which covers international formats while rejecting short codes and
    malformed strings.

    Args:
        html: Raw HTML string for one page.

    Returns:
        Set of phone number strings as they appeared in the tel: href.
    """
    out: set[str] = set()
    for raw in _TEL_RE.findall(html):
        phone = raw.strip()
        digits = re.sub(r"\D", "", phone)
        if 7 <= len(digits) <= 15:
            out.add(phone)
    return out


class SocialAgent:
    """Discovers social accounts, team members, and contact details from a website.

    Instantiated with optional proxy and JS-rendering settings so the same
    class can be used for simple static sites (render_js=False) and
    JavaScript-heavy SPAs (render_js=True) without code changes.
    """

    def __init__(self, proxy: str | None = None, render_js: bool = False) -> None:
        self._proxy = proxy
        # render_js controls whether Playwright is used instead of plain httpx.
        # Default False because most company sites expose social links in
        # static HTML and JS rendering adds significant latency.
        self._render_js = render_js

    @staticmethod
    def _domain(url: str) -> str:
        try:
            return urlparse(url).netloc.lower().replace("www.", "")
        except Exception:
            return ""

    async def _fetch(
        self, urls: list[str], render_js: bool
    ) -> list[tuple[str, str]]:
        """Fetch raw HTML for a batch of URLs in one Scraper call.

        Batching (rather than one URL at a time) allows the Scraper to
        parallelise requests internally and reuse connections.  A catch-all
        exception returns an empty list so a network failure on one batch
        does not abort the entire agent run.

        Args:
            urls: List of absolute URLs to fetch.
            render_js: Whether to use Playwright for JavaScript rendering.

        Returns:
            List of (final_url, html) tuples — only for responses that
            returned non-empty HTML.  The final_url may differ from the
            input URL after redirects.
        """
        if not urls:
            return []
        scraper = Scraper(proxy=self._proxy, render_js=render_js)
        try:
            results = await scraper.scrape_urls(urls)
        except Exception as exc:
            logger.warning("social_agent.fetch_failed", error=str(exc))
            return []
        return [(r.url, r.html) for r in results if r.html]

    def _scan(
        self,
        html: str,
        base_url: str,
        domain: str,
        socials: dict[str, tuple[str, str]],
        info_pages: list[str],
    ) -> None:
        """Scan one page's raw HTML for org social links and info-page links.

        Mutates the shared ``socials`` dict and ``info_pages`` list in-place
        so results accumulate across multiple pages without re-allocating.

        Social discovery uses _SOCIAL_RE (LinkedIn /company/ + Instagram
        handles) against the full raw HTML — this catches URLs embedded in
        JSON data attributes and inline scripts, not just visible <a> tags.

        Info-page discovery uses raw href extraction and checks each resolved
        URL's path segments against _INFO_SEGMENTS.  Only same-domain links
        are added (external hrefs are discarded) and the list is capped at
        _MAX_INFO_PAGES to bound the total number of fetches per run.

        Args:
            html: Raw HTML string for the page.
            base_url: Absolute URL of this page (used to resolve relative hrefs).
            domain: Registered domain of the subject (e.g. "acme.com") used
                    to filter out cross-domain links.
            socials: Accumulator dict {normalized_url: (platform, profile_type)}.
            info_pages: Accumulator list of normalized info-page URLs to fetch next.
        """
        for match in _SOCIAL_RE.findall(html):
            url = _norm(match)
            cls = _classify(url)
            if cls and url not in socials:
                socials[url] = cls

        for href in _HREF_RE.findall(html):
            if href.startswith(("mailto:", "tel:", "javascript:", "#", "data:")):
                continue
            full = urljoin(base_url, href)
            # Discard cross-domain links — we only crawl the subject's own site.
            if self._domain(full) != domain:
                continue
            segments = [s for s in urlparse(full).path.lower().split("/") if s]
            if any(s in _INFO_SEGMENTS for s in segments):
                norm = _norm(full)
                if norm not in info_pages and len(info_pages) < _MAX_INFO_PAGES:
                    info_pages.append(norm)

    @staticmethod
    def _name_near(node) -> str:
        """Climb DOM ancestors looking for a heading that reads like a human name.

        Used when a LinkedIn /in/ link has no text of its own (e.g. a button
        with only an icon).  Walking up to 4 ancestor levels catches typical
        team-card structures like:
          <div class="team-card">
            <h4>Jane Smith</h4>
            <a href="linkedin.com/in/..."><icon/></a>
          </div>

        Args:
            node: BeautifulSoup element (the <a> or other anchor).

        Returns:
            The name string if found, otherwise an empty string.
        """
        current = node
        for _ in range(4):
            current = getattr(current, "parent", None)
            if current is None:
                break
            # Check only the first 6 headings to avoid scanning huge blocks.
            for h in current.find_all(
                ["h1", "h2", "h3", "h4", "h5", "strong", "b"], recursive=True
            )[:6]:
                text = h.get_text(" ", strip=True)
                if _looks_like_name(text):
                    return text
        return ""

    @staticmethod
    def _title_near(node) -> str:
        """Best-effort job title from the sibling element immediately after a name node.

        Looks forward up to 3 siblings for a short text block that is NOT
        itself a name (to avoid reading the next person's name as the title).

        Args:
            node: BeautifulSoup element whose next siblings are inspected.

        Returns:
            Title string (2–90 chars) if found, otherwise an empty string.
        """
        sibling = node.find_next_sibling()
        hops = 0
        while sibling is not None and hops < 3:
            text = (
                sibling.get_text(" ", strip=True)
                if hasattr(sibling, "get_text")
                else ""
            )
            if text and 2 <= len(text) <= 90 and not _looks_like_name(text):
                return text
            sibling = (
                sibling.find_next_sibling()
                if hasattr(sibling, "find_next_sibling")
                else None
            )
            hops += 1
        return ""

    def _extract_people(
        self, html: str, page_url: str, seen: set[str]
    ) -> list[PersonContact]:
        """Extract real team members from a page using three ranked strategies.

        The ``seen`` set is shared across all pages in one run so the same
        person is not returned twice; a second mention with a LinkedIn URL
        will enrich the existing record (name-match lookup) rather than
        duplicate it.

        Strategy priority (highest confidence first):
          1. JSON-LD Person schema — structured, machine-readable data
          2. LinkedIn /in/ anchor links — an explicit person link is strong signal
          3. Team-card name headings — heuristic, limited to verified team pages

        Args:
            html: Raw HTML string for one page.
            page_url: The URL of this page (used as a data source label and for
                      resolving relative LinkedIn hrefs).
            seen: Mutable set of lowercased names already recorded; updated in-place.

        Returns:
            New PersonContact objects found on this page (excluding already-seen names).
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return []

        people: list[PersonContact] = []

        def add(name: str, title: str = "", linkedin: str = "") -> None:
            """Add a person or enrich an existing record with their LinkedIn URL."""
            name = " ".join((name or "").split())
            if not name:
                return
            key = name.lower()
            if key in seen:
                # Already recorded — enrich with LinkedIn URL if we now have one.
                if linkedin:
                    for p in people:
                        if p.name.lower() == key and not p.linkedin_url:
                            p.linkedin_url = linkedin
                return
            seen.add(key)
            people.append(
                PersonContact(
                    name=name[:120],
                    title=" ".join((title or "").split())[:160],
                    linkedin_url=linkedin,
                    source=page_url,
                )
            )

        # ---- Strategy 1: JSON-LD Person schema markup ----
        # The most structured and reliable source.  Many company sites embed
        # schema.org/Person objects for SEO; these include name, jobTitle, and
        # sameAs links (which often contain the LinkedIn /in/ URL).
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = script.string or script.get_text() or ""
            try:
                parsed = json.loads(raw)
            except Exception:
                continue
            for obj in _iter_jsonld(parsed):
                types = obj.get("@type")
                types = [types] if isinstance(types, str) else (types or [])
                if "Person" not in types or not obj.get("name"):
                    continue
                linkedin = ""
                same = obj.get("sameAs") or []
                same = [same] if isinstance(same, str) else same
                for s in same:
                    if isinstance(s, str) and "linkedin.com/in/" in s.lower():
                        linkedin = _norm(s)
                add(str(obj.get("name")), str(obj.get("jobTitle") or ""), linkedin)

        # ---- Strategy 2: LinkedIn /in/ anchor links ----
        # Any link to linkedin.com/in/<handle> is almost certainly a real person.
        # Prefer the anchor's own text; fall back to _name_near if it is empty
        # (e.g. an icon-only button).
        for a in soup.find_all("a", href=True):
            if "linkedin.com/in/" not in a["href"].lower():
                continue
            text = a.get_text(" ", strip=True)
            name = text if _looks_like_name(text) else self._name_near(a)
            if name:
                add(name, self._title_near(a), _norm(urljoin(page_url, a["href"])))

        # ---- Strategy 3: Team-card name headings (team pages only) ----
        # Heuristic: look for elements with team/member/person CSS classes and
        # scan their headings for name-shaped text.  This is restricted to
        # pages whose URL path contains a known team segment (_TEAM_PATH_SEGMENTS)
        # because homepages carry too much name-shaped noise (product titles,
        # customer quotes, etc.) for this approach to be reliable there.
        segments = urlparse(page_url).path.lower().split("/")
        is_team_page = any(seg in _TEAM_PATH_SEGMENTS for seg in segments)
        if is_team_page:
            for container in soup.find_all(class_=_PERSON_CONTAINER_RE)[:300]:
                if len(people) >= _MAX_PEOPLE:
                    break
                for h in container.find_all(
                    ["h2", "h3", "h4", "h5", "strong", "b"], recursive=True
                ):
                    text = h.get_text(" ", strip=True)
                    if _looks_like_name(text):
                        # break after the first name in a card — subsequent
                        # headings in the same card are likely titles or sections.
                        add(text, self._title_near(h))
                        break

        return people

    async def run(
        self,
        *,
        subject_type: str,
        subject_name: str,
        website: str,
        subject_id: uuid.UUID | None = None,
    ) -> SubjectSocials:
        """Crawl one subject's site and harvest social accounts, people, and contacts.

        Crawl sequence:
          1. Homepage — discover org social links and identify team/info pages.
          2. Team / about / contact pages (up to _MAX_INFO_PAGES) — repeat scan.
          3. Extract people from all fetched pages using the three-strategy extractor.
          4. Extract emails and phones from all fetched pages.
          5. Assemble a SubjectSocials result object.

        Args:
            subject_type: "company" or "competitor" — stored in the result for
                          the API consumer to distinguish sources.
            subject_name: Display name of the subject (for logging).
            website: Homepage URL (with or without scheme; bare domains are fine).
            subject_id: Optional UUID to link the result back to a DB record.

        Returns:
            SubjectSocials with profiles, people, emails, and phones populated.
            Returns an empty SubjectSocials (no data) if website is blank.
        """
        website = (website or "").strip()
        result = SubjectSocials(
            subject_type=subject_type,
            subject_id=subject_id,
            subject_name=subject_name,
            website=website,
        )
        if not website:
            logger.info("social_agent.skip", subject=subject_name, reason="no website")
            return result

        t0 = time.perf_counter()
        website = _ensure_scheme(website)
        domain = self._domain(website)
        socials: dict[str, tuple[str, str]] = {}
        info_pages: list[str] = []

        # 1. Homepage — discover org socials + team/about/contact page links.
        home = await self._fetch([website], self._render_js)
        for final_url, html in home:
            self._scan(html, final_url, domain, socials, info_pages)

        # 2. Team / about / contact pages.
        extra: list[tuple[str, str]] = []
        if info_pages:
            extra = await self._fetch(info_pages, self._render_js)
            for final_url, html in extra:
                self._scan(html, final_url, domain, socials, [])

        all_pages = home + extra

        # 3. People — from every fetched page.
        seen_people: set[str] = set()
        people: list[PersonContact] = []
        for url, html in all_pages:
            for person in self._extract_people(html, url, seen_people):
                people.append(person)
            if len(people) >= _MAX_PEOPLE:
                break

        # 4. Emails + phones — from every fetched page.
        emails: set[str] = set()
        phones: set[str] = set()
        for _url, html in all_pages:
            emails |= _extract_emails(html)
            phones |= _extract_phones(html)

        # ---- Assemble result ----
        # Social profiles are recorded as discovered links only (success=False).
        # Deep account scraping (post count, follower count, etc.) is handled
        # separately by the on-demand /scrapers endpoints, not the pipeline.
        for url, (platform, _ptype) in socials.items():
            result.profiles.append(
                SocialProfileData(
                    platform=platform,
                    profile_type="organization",
                    url=url,
                    success=False,
                    source="website",
                    data={"url": url, "discovered": True},
                )
            )
        result.people = people[:_MAX_PEOPLE]
        result.emails = sorted(emails)[:_MAX_EMAILS]
        result.phones = sorted(phones)[:10]

        logger.info(
            "social_agent.done",
            subject=subject_name,
            accounts=len(result.profiles),
            people=len(result.people),
            emails=len(result.emails),
            phones=len(result.phones),
            elapsed=round(time.perf_counter() - t0, 2),
        )
        return result
