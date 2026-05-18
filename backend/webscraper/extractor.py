"""HTML parsing and data-cleaning pipeline for scraped web pages.

After scraper.py retrieves raw HTML, this module turns it into a structured
Python dict that the pipeline agents can reason over.

Extraction strategy:
  1. _get_content_root() detects the "main content" region of the page using
     a prioritised list of CSS selectors (article, [role='main'], #content, …).
     Junk regions (nav, footer, ads, scripts, Wikipedia sidebars, cookie banners)
     are stripped from the clone before any text is read.
  2. Extraction helpers pull typed data: title, meta description, headings (h1–h6),
     paragraph text, links, images, HTML tables, JSON-LD structured data, and
     all <meta> tags.
  3. _clean() normalises whitespace throughout.

The output dict is consumed by:
  - scraper_standalone.py  → /api/scrape endpoint response body.
  - app/agents/web_agent.py → fed into the LLM prompt as structured context.
"""

from __future__ import annotations

import re
import json
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment, Tag


def extract(html: str, url: str) -> dict:
    """Parse raw HTML into a structured data dictionary.

    This is the single public entry point of this module.  It accepts the HTML
    string returned by scraper.py and the final URL (used to resolve relative
    links and images), and returns a dict with well-defined keys for every
    content type extracted.

    Args:
        html: Raw HTML string (decoded by scraper._decode_response).
        url:  The page's final URL after redirects (used as base for urljoin).

    Returns:
        dict with keys:
            url, title, meta_description, headings, paragraphs,
            text_content, links, images, tables, structured_data, meta_tags.
    """
    soup = BeautifulSoup(html, "lxml")

    # Build a clean content subtree for text extraction.
    # This strips junk (nav, ads, scripts) before any data is read.
    content_soup = _get_content_root(soup)

    return {
        "url": url,
        "title": _get_title(soup),
        "meta_description": _get_meta(soup, "description"),
        "headings": _get_headings(content_soup),
        "paragraphs": _get_paragraphs(content_soup),
        "text_content": _get_text(content_soup),
        "links": _get_links(content_soup, url),
        "images": _get_images(content_soup, url),
        "tables": _get_tables(content_soup),
        "structured_data": _get_structured_data(soup),  # parsed from full doc, not content subtree
        "meta_tags": _get_all_meta(soup),               # parsed from full doc
    }


# ---------------------------------------------------------------------------
# Main content detection
# ---------------------------------------------------------------------------

# Tags whose entire subtree is noise (JavaScript, styles, hidden elements,
# navigation chrome). These are removed before any text is extracted.
_JUNK_TAGS = [
    "script", "style", "noscript", "svg", "template",
    "nav", "footer", "header", "aside",
    "iframe", "object", "embed",
]

# CSS selectors for common chrome and Wikipedia-specific clutter.
# Evaluated after tag removal to catch role-attribute and class-based junk.
_JUNK_SELECTORS = [
    "[role='navigation']", "[role='banner']", "[role='contentinfo']",
    "[role='complementary']", "[aria-hidden='true']",
    ".sidebar", "#sidebar", ".nav", ".navbar", ".navigation",
    ".menu", ".header", ".footer", ".toc", "#toc",
    ".mw-jump-link", "#catlinks", "#mw-navigation", "#mw-panel",
    ".navbox", ".sistersitebox", ".mw-editsection", ".reflist",
    ".references", ".external", ".mw-authority-control",
    ".mw-indicators", ".noprint", ".cookie-banner", ".cookie-consent",
    ".ad", ".ads", ".advertisement", "#comments", ".comments",
]

# Ordered list of CSS selectors that identify the main content region.
# The first match wins; if none match, the full <body> is used.
_CONTENT_SELECTORS = [
    "#mw-content-text", "article", "[role='main']", "main",
    "#content", "#main-content", ".main-content", ".post-content",
    ".article-content", ".entry-content", ".page-content", "#bodyContent",
]


def _get_content_root(soup: BeautifulSoup) -> BeautifulSoup:
    """Return a cleaned copy of the most likely content subtree.

    Steps:
      1. Walk _CONTENT_SELECTORS in priority order; take the first match.
         Falls back to <body>, then the whole document if neither is found.
      2. Clone the subtree as a new BeautifulSoup object (str → re-parse)
         so the original soup is not mutated.
      3. Decompose all junk tags and junk-selector elements in the clone.
      4. Strip HTML comments (<!-- ... -->) which carry no useful text.

    Args:
        soup: Full parsed document.

    Returns:
        Cleaned BeautifulSoup subtree ready for text extraction.
    """
    root = None
    for sel in _CONTENT_SELECTORS:
        root = soup.select_one(sel)
        if root: break

    # No known content selector found — fall back to the whole body.
    if root is None:
        root = soup.find("body") or soup

    # Clone the subtree so the original soup stays intact for meta/title extraction.
    clone = BeautifulSoup(str(root), "lxml")

    # Remove entire tag families (scripts, styles, nav, …).
    for tag in clone.find_all(_JUNK_TAGS):
        tag.decompose()

    # Remove role/class-based junk that survived the tag sweep.
    for sel in _JUNK_SELECTORS:
        for el in clone.select(sel):
            el.decompose()

    # HTML comments carry no visible text and can contain conditional IE markup.
    for comment in clone.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    return clone


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _get_title(soup: BeautifulSoup) -> str:
    """Return the text content of the <title> element, cleaned."""
    tag = soup.find("title")
    return _clean(tag.get_text()) if tag else ""


def _get_meta(soup: BeautifulSoup, name: str) -> str:
    """Return the content= value of a named <meta> tag (case-insensitive match).

    Args:
        soup: Document soup (not content subtree — meta tags live in <head>).
        name: The value of the name= attribute to look up (e.g. "description").
    """
    tag = soup.find("meta", attrs={"name": re.compile(f"^{name}$", re.I)})
    if tag:
        return _clean(tag.get("content", ""))
    return ""


def _get_headings(soup: BeautifulSoup) -> dict[str, list[str]]:
    """Extract all heading text grouped by level (h1 through h6).

    Returns:
        Dict mapping tag name to list of non-empty heading strings,
        e.g. {"h1": ["About Us"], "h2": ["Our Team", "History"]}.
        Levels with no headings are omitted from the dict.
    """
    headings: dict[str, list[str]] = {}
    for level in range(1, 7):
        tag_name = f"h{level}"
        found = [_clean(h.get_text()) for h in soup.find_all(tag_name)]
        found = [h for h in found if h]  # Drop empty strings after cleaning.
        if found:
            headings[tag_name] = found
    return headings


def _get_paragraphs(soup: BeautifulSoup) -> list[str]:
    """Extract non-trivial paragraph text (> 20 characters after cleaning).

    The 20-character minimum filters out decorative or single-word <p> tags
    (e.g. copyright symbols, button labels) that have no informational value.
    """
    paragraphs = []
    for p in soup.find_all("p"):
        text = _clean(p.get_text())
        if text and len(text) > 20:
            paragraphs.append(text)
    return paragraphs


def _get_text(soup: BeautifulSoup) -> str:
    """Build a single clean text string from all visible content.

    Rather than calling soup.get_text() (which loses block structure), this
    walks every descendant node manually and inserts newlines at block-level
    boundaries. This preserves paragraph and heading breaks in the output,
    which helps the LLM parse the content more accurately.

    Returns:
        Multi-line string with whitespace normalised:
        - Multiple spaces/tabs collapsed to one space.
        - Multiple blank lines collapsed to one blank line.
    """
    _BLOCK_TAGS = {
        "p", "div", "section", "article", "blockquote",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "li", "tr", "td", "th", "dt", "dd",
        "pre", "figure", "figcaption", "details", "summary",
    }
    parts: list[str] = []
    for element in soup.descendants:
        if isinstance(element, str):
            text = element.strip()
            if text: parts.append(text)
        elif isinstance(element, Tag) and element.name in _BLOCK_TAGS:
            # Insert a logical line break before each block-level element
            # so its text starts on a new "line" in the joined output.
            parts.append("\n")

    raw = " ".join(parts)
    raw = re.sub(r"[ \t]+", " ", raw)      # Collapse runs of spaces/tabs.
    raw = re.sub(r" ?\n ?", "\n", raw)     # Clean up space around newlines.
    raw = re.sub(r"\n{3,}", "\n\n", raw)   # No more than one blank line.
    return raw.strip()


def _get_links(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Extract all clickable links from the content subtree.

    Non-navigable href schemes (javascript:, mailto:, tel:, fragment-only #)
    are filtered out because they carry no crawlable destination.

    Relative URLs are resolved against base_url so the result always contains
    absolute URLs the pipeline can act on.

    Returns:
        List of dicts: [{"text": "...", "href": "https://..."}, ...]
    """
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        # Skip non-HTTP links that cannot be crawled.
        if href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        links.append({
            "text": _clean(a.get_text()),
            "href": urljoin(base_url, href),  # Resolve relative paths.
        })
    return links


def _get_images(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Extract image alt text and src from <img> tags.

    Relative src values are resolved to absolute URLs using base_url.

    Returns:
        List of dicts: [{"alt": "...", "src": "https://..."}, ...]
    """
    images = []
    for img in soup.find_all("img", src=True):
        images.append({
            "alt": _clean(img.get("alt", "")),
            "src": urljoin(base_url, img["src"].strip()),
        })
    return images


def _get_tables(soup: BeautifulSoup) -> list[list[list[str]]]:
    """Extract table data as a nested list structure.

    Returns a 3D list: tables → rows → cells.
    Both <td> and <th> are treated as cells so header rows are included.
    Empty tables (no rows with content) are omitted.

    Returns:
        list[table][row][cell]  — e.g. [[["Name", "Price"], ["Widget", "$5"]]]
    """
    tables = []
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [_clean(td.get_text()) for td in tr.find_all(["td", "th"])]
            if any(cells):  # Skip rows that are entirely empty.
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def _get_structured_data(soup: BeautifulSoup) -> list[dict]:
    """Extract JSON-LD structured data blocks embedded in the page.

    JSON-LD (application/ld+json) is the standard machine-readable format
    used by websites to describe entities (Product, Organization, Person, etc.)
    for search engines. Extracting it gives the pipeline rich semantic data
    without HTML parsing heuristics.

    Malformed JSON blocks are silently skipped.

    Returns:
        List of parsed JSON objects (dicts), one per valid <script> block.
    """
    results = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if data: results.append(data)
        except:
            continue
    return results


def _get_all_meta(soup: BeautifulSoup) -> dict[str, str]:
    """Collect all <meta> tags into a flat name→value dict.

    Recognises three attribute patterns for the key:
      - name=       (standard HTML meta: description, robots, …)
      - property=   (Open Graph: og:title, og:description, …)
      - http-equiv= (legacy directives: refresh, content-type, …)

    Tags without a key or content attribute are ignored.

    Returns:
        Dict mapping the meta key to its content value (both cleaned).
    """
    meta = {}
    for tag in soup.find_all("meta"):
        key = tag.get("name") or tag.get("property") or tag.get("http-equiv")
        content = tag.get("content", "")
        if key and content:
            meta[key] = _clean(content)
    return meta


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    """Normalise whitespace in a text string.

    Strips leading/trailing whitespace, collapses internal horizontal
    whitespace runs to a single space, and limits vertical whitespace to
    at most two consecutive newlines.

    Args:
        text: Raw text extracted from an HTML node.

    Returns:
        Cleaned string.
    """
    text = text.strip()
    text = re.sub(r"[ \t]+", " ", text)    # Collapse spaces and tabs.
    text = re.sub(r"\n{3,}", "\n\n", text)  # No more than one blank line.
    return text
