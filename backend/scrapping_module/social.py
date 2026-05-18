"""Social-media scraper — multi-strategy approach with LinkedIn bypass.

This module is the production social-scraping path.  It is called by
app/services/scraping_service.py, which is invoked by the pipeline's
SocialAgent to enrich competitor and persona data with social-profile info.

Why not scrape LinkedIn directly?
  LinkedIn requires authentication for most profile data and aggressively
  blocks bots with HTTP 999 / 403 responses and JavaScript challenges.
  Direct scraping is legally grey and technically very difficult.
  Instead, we exploit the fact that Google's search index contains LinkedIn
  profile summaries (name, headline, about snippet) and Google is far easier
  to scrape than LinkedIn itself.

Strategy order for LinkedIn:
  1. Google SERP (httpx)       — Parse the search-result snippet for the
                                  profile URL; this gives name + headline + about
                                  with zero authentication.
  2. Google Cache (httpx)      — If the SERP snippet was thin, fetch Google's
                                  cached copy of the LinkedIn page and read the
                                  og:title / og:description meta tags.
  (No Playwright fallback for LinkedIn — it adds risk without much gain since
  LinkedIn blocks headless browsers just as aggressively.)

Strategy order for Instagram:
  1. Unofficial API (httpx)    — Call /api/v1/users/web_profile_info/ after
                                  collecting a session cookie and CSRF token.
  2. Embedded JSON (httpx)     — Regex-extract window.__additionalDataLoaded or
                                  window._sharedData from the page source.
  3. Playwright + intercept    — Launch a headless browser, intercept every
                                  network response, and capture the GQL/API
                                  JSON payloads before they reach the page JS.

Threading note:
  The Instagram Playwright strategy uses sync_playwright in a ThreadPoolExecutor
  because on Windows the asyncio event loop running uvicorn cannot spawn
  the subprocess that Playwright requires.  Running it in a thread sidesteps
  this limitation while keeping the public API fully async.
"""

import asyncio
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from bs4 import BeautifulSoup

import httpx

# Ensure the project root is on sys.path so config.py can be imported
# regardless of the working directory the module is loaded from.
sys.path.append(str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright
from webscraper import config

# Shared thread pool: Instagram's Playwright strategy runs synchronous
# Playwright inside threads.  Two workers is enough for typical batch sizes
# and avoids exhausting system resources with too many browser instances.
_executor = ThreadPoolExecutor(max_workers=2)


# ------------------------------------------------------------------
# LinkedIn Bypass — httpx strategies (no browser needed)
# ------------------------------------------------------------------

def _scrape_linkedin_via_google(url: str, proxy: str | None) -> dict:
    """Retrieve LinkedIn profile data indirectly via Google Search results.

    LinkedIn blocks unauthenticated scraping, but Google indexes every public
    LinkedIn profile and returns a rich snippet (name, title, about text) in
    its search result cards.  This function:
      1. Searches Google for the LinkedIn profile URL.
      2. Parses the SERP HTML to find the result card that links to the profile.
      3. Reads the <h3> title (which LinkedIn formats as "Name - Title | LinkedIn")
         and the snippet element to extract name, headline, and about text.
      4. Falls back to Google's cached copy of the page (webcache.googleusercontent.com)
         to read og:title / og:description if the SERP snippet is insufficient.

    This approach requires no LinkedIn credentials and no headless browser.

    Args:
        url:   LinkedIn profile URL, e.g. "https://www.linkedin.com/in/username/".
        proxy: Optional proxy URL to route requests through.

    Returns:
        dict with keys: platform, url, profile_name, headline, location, about,
        avatar, experience, source.  Returns {} if the profile could not be found.
        Returns {"error": ..., "url": ...} on network/parsing exceptions.
    """
    # Extract the profile slug from the URL (the part after /in/).
    username = url.rstrip("/").split("/in/")[-1].rstrip("/")

    # Construct a Google search that targets the exact LinkedIn profile page.
    search_query = f'linkedin.com/in/{username}'
    search_url = f"https://www.google.com/search?q={search_query}&hl=en&num=3"

    # Headers that make the request look like Chrome on Windows.
    # Google is more likely to serve full SERP HTML to requests that resemble
    # a real browser — User-Agent and Sec-Fetch-* headers are especially checked.
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
    }

    try:
        with httpx.Client(
            headers=headers,
            follow_redirects=True,
            timeout=15,
            proxies=proxy,
        ) as client:
            resp = client.get(search_url)
            if resp.status_code != 200:
                return {}

            soup = BeautifulSoup(resp.text, "html.parser")

            profile_name = ""
            headline = ""
            about = ""
            avatar = ""

            # Strategy A: Parse Google Knowledge Panel / organic search result card.
            # Each result is wrapped in div.g or div[data-hveid]; we find the one
            # that contains a link to the LinkedIn profile we want.
            for result in soup.select("div.g, div[data-hveid]"):
                # Check if this result card links to the target LinkedIn profile.
                link = result.find("a", href=re.compile(r"linkedin\.com/in/", re.I))
                if not link:
                    continue

                # The <h3> contains the page title; LinkedIn formats it as:
                # "First Last - Job Title · Company | LinkedIn"
                h3 = result.find("h3")
                if h3:
                    raw_title = h3.get_text(strip=True)
                    # Strip the LinkedIn branding suffix before parsing.
                    raw_title = raw_title.replace("| LinkedIn", "").replace("LinkedIn", "").strip(" |·")
                    if " - " in raw_title:
                        # Most common format: "Name - Headline"
                        parts = raw_title.split(" - ", 1)
                        profile_name = parts[0].strip()
                        headline = parts[1].strip(" ·|")
                    elif " · " in raw_title:
                        # Alternate separator: "Name · Headline"
                        parts = raw_title.split(" · ", 1)
                        profile_name = parts[0].strip()
                        headline = parts[1].strip()
                    else:
                        profile_name = raw_title

                # The snippet div contains the "about" summary text shown in the SERP.
                snippet_el = result.select_one("div.VwiC3b, span.aCOpRe, div[style*='webkit-line-clamp']")
                if snippet_el:
                    about = snippet_el.get_text(strip=True)

                # Stop at the first valid profile card (not a generic LinkedIn page).
                if profile_name and profile_name.lower() not in ("sign up", "join linkedin", "linkedin"):
                    break

            # Strategy B: Google Cache fallback.
            # If Strategy A produced no name (e.g. the SERP card was thin or absent),
            # fetch Google's cached snapshot of the LinkedIn page.  The cached page
            # still has og:title / og:description meta tags with the profile data.
            if not profile_name:
                cache_headers = {**headers, "Referer": "https://www.google.com/"}
                cache_url = f"https://webcache.googleusercontent.com/search?q=cache:linkedin.com/in/{username}&hl=en"
                try:
                    cache_resp = client.get(cache_url, headers=cache_headers)
                    if cache_resp.status_code == 200:
                        csoup = BeautifulSoup(cache_resp.text, "html.parser")
                        og = csoup.find("meta", property="og:title")
                        if og and og.get("content"):
                            raw = og["content"].replace("| LinkedIn", "").strip()
                            if " - " in raw:
                                parts = raw.split(" - ", 1)
                                profile_name = parts[0].strip()
                                headline = parts[1].strip()
                            else:
                                profile_name = raw
                        desc = csoup.find("meta", property="og:description")
                        if desc:
                            about = (desc.get("content") or "").strip()
                        img = csoup.find("meta", property="og:image")
                        if img:
                            v = img.get("content", "")
                            # Exclude favicons — they are generic LinkedIn icons, not profile photos.
                            avatar = v if "favicon" not in v else ""
                except Exception:
                    pass

            # Guard against Google returning its own login/landing pages.
            if not profile_name or profile_name.lower() in ("sign up", "join linkedin", "linkedin", ""):
                return {}

            return {
                "platform": "LinkedIn",
                "url": url,
                "profile_name": profile_name,
                "headline": headline,
                "location": "",       # Location is not reliably available in SERP snippets.
                "about": about,
                "avatar": avatar,
                "experience": [],     # Experience requires authenticated LinkedIn access.
                "source": "Google SERP",
            }

    except Exception as e:
        return {"error": str(e), "url": url}

    return {}


# ------------------------------------------------------------------
# Instagram scraper — multi-strategy
# ------------------------------------------------------------------

# HTTP headers that mimic an authenticated Instagram browser session.
# X-IG-App-ID is Instagram's public web app ID used in their internal API calls.
# X-Requested-With: XMLHttpRequest tells Instagram's API this is an AJAX request.
_IG_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.instagram.com/",
    "X-IG-App-ID": "936619743392459",    # Instagram's public web app identifier.
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


def _parse_ig_user_data(user: dict, url: str, extra_posts: list | None = None) -> dict:
    """Normalise an Instagram API user object into the standard profile dict.

    Instagram has changed its API response structure multiple times; this
    function handles both the old edge-based format (edge_followed_by.count)
    and the newer flat format (follower_count) for all numeric fields, and
    similarly for post nodes (edge_owner_to_timeline_media vs direct items).

    Args:
        user:        Raw user dict from any Instagram API or GQL response.
        url:         Original profile URL (preserved in the output).
        extra_posts: Additional post nodes captured from a separate GQL
                     timeline response (injected by the browser strategy).

    Returns:
        Normalised dict with keys: platform, url, username, full_name, bio,
        avatar, followers, following, posts_count, is_verified, is_private,
        external_url, latest_posts, type.
    """
    import datetime

    username = user.get("username", "")
    full_name = user.get("full_name", "")
    bio = user.get("biography", "")
    avatar = user.get("profile_pic_url_hd", "") or user.get("profile_pic_url", "")
    is_verified = user.get("is_verified", False)
    is_private = user.get("is_private", False)
    external_url = user.get("external_url", "")

    # Follower/following counts: try new flat field first, then old nested edge format.
    followers = (
        user.get("follower_count")
        or user.get("edge_followed_by", {}).get("count", 0)
    )
    following = (
        user.get("following_count")
        or user.get("edge_follow", {}).get("count", 0)
    )
    posts_count = (
        user.get("media_count")
        or user.get("edge_owner_to_timeline_media", {}).get("count", 0)
    )

    # --- Posts: collect from whichever format is present ---
    posts = []
    edges = user.get("edge_owner_to_timeline_media", {}).get("edges", [])

    # Some API versions use edge_felix_video_timeline for Reels/Videos.
    if not edges:
        edges = user.get("edge_felix_video_timeline", {}).get("edges", [])

    # extra_posts are captured from separate GQL requests by the browser strategy.
    if not edges and extra_posts:
        edges = extra_posts

    for edge in edges[:10]:  # Limit to 10 most recent posts for speed.
        node = edge.get("node", {}) if isinstance(edge, dict) and "node" in edge else edge
        if not node:
            continue

        # Caption: old format stores it under edge_media_to_caption.edges[0].node.text.
        caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
        caption = caption_edges[0]["node"]["text"] if caption_edges else node.get("caption", "")
        if isinstance(caption, dict):
            caption = caption.get("text", "")
        caption = caption or ""

        # Like/comment counts: try new flat fields, fall back to old edge counts.
        likes = (
            node.get("like_count")
            or node.get("edge_liked_by", {}).get("count")
            or node.get("edge_media_preview_like", {}).get("count", 0)
        )
        comments = (
            node.get("comment_count")
            or node.get("edge_media_to_comment", {}).get("count", 0)
        )

        # Media URL: use HD display URL, fall back to first candidate from image_versions2.
        media_url = node.get("display_url", "") or node.get("image_versions2", {}).get("candidates", [{}])[0].get("url", "")
        thumbnail = node.get("thumbnail_src", "") or media_url

        # Timestamp: old format uses taken_at_timestamp (Unix epoch), new uses taken_at.
        ts = node.get("taken_at_timestamp") or node.get("taken_at", 0)
        dt = datetime.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M") if ts else ""

        # Map __typename (old) or media_type integer (new) to a human-readable label.
        typename = node.get("__typename", "") or node.get("media_type", "")
        type_map = {
            "GraphImage": "Photo", "GraphVideo": "Video", "GraphSidecar": "Carousel",
            1: "Photo", 2: "Video", 8: "Carousel"
        }
        post_type = type_map.get(typename, "Photo")

        shortcode = node.get("shortcode", "") or node.get("code", "")

        posts.append({
            "shortcode": shortcode,
            "url": f"https://www.instagram.com/p/{shortcode}/" if shortcode else "",
            "type": post_type,
            "caption": caption[:300] + ("..." if len(caption) > 300 else ""),
            "likes": likes,
            "comments": comments,
            "media_url": thumbnail,
            "posted_at": dt,
        })

    return {
        "platform": "Instagram",
        "url": url,
        "username": username,
        "full_name": full_name,
        "bio": bio,
        "avatar": avatar,
        "followers": followers,
        "following": following,
        "posts_count": posts_count,
        "is_verified": is_verified,
        "is_private": is_private,
        "external_url": external_url,
        "latest_posts": posts,
        "type": "Profile",
    }


def _scrape_instagram_api(url: str, proxy: str | None) -> dict:
    """Strategy 1: Instagram's unofficial web_profile_info API endpoint.

    Instagram's internal web app calls /api/v1/users/web_profile_info/?username=X
    to render profile pages.  This endpoint is not officially public but is
    accessible if the request includes:
      - A valid session cookie (csrftoken, sessionid, etc.) obtained by first
        visiting instagram.com with a plain GET request.
      - The X-CSRFToken header matching the csrftoken cookie value.
      - The X-IG-App-ID header matching Instagram's known web app ID.

    This is the fastest strategy (no browser, no JS rendering) and returns
    structured JSON that _parse_ig_user_data can consume directly.

    Args:
        url:   Instagram profile URL.
        proxy: Optional proxy URL.

    Returns:
        Normalised profile dict, or {} if the endpoint refused or errored.
    """
    username = url.rstrip("/").split("/")[-1].lstrip("@")
    # Strip query parameters (e.g. ?hl=en) from the extracted username.
    username = username.split("?")[0]

    api_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"

    try:
        with httpx.Client(
            headers={
                "User-Agent": _IG_HEADERS["User-Agent"],
                "Accept-Language": "en-US,en;q=0.9",
            },
            follow_redirects=True,
            timeout=15,
            proxies=proxy,
        ) as client:
            # Step 1: Visit the Instagram homepage to receive session cookies.
            # Instagram sets csrftoken on the first visit; we need it to call the API.
            home_resp = client.get("https://www.instagram.com/")
            csrf = ""
            for cookie in client.cookies.jar:
                if cookie.name == "csrftoken":
                    csrf = cookie.value
                    break

            # Step 2: Call the API with the session cookie and CSRF token.
            api_headers = {
                **_IG_HEADERS,
                "X-CSRFToken": csrf,
                # Forward all cookies from the session as a single Cookie header.
                "Cookie": "; ".join([f"{c.name}={c.value}" for c in client.cookies.jar]),
            }

            resp = client.get(api_url, headers=api_headers)
            if resp.status_code == 200:
                data = resp.json()
                user = data.get("data", {}).get("user", {})
                if user:
                    return _parse_ig_user_data(user, url)
    except Exception:
        pass
    return {}


def _scrape_instagram_json_embed(url: str, proxy: str | None) -> dict:
    """Strategy 2: Extract embedded JSON blobs from the Instagram page source.

    Instagram's page HTML contains several JavaScript variable assignments that
    hold the full profile data as JSON.  We look for three known patterns with
    a regex search, then walk the nested structure to find the user object.

    If no JSON blob is found (Instagram frequently removes/obfuscates these),
    we fall back to reading the og:title and og:description Open Graph meta tags,
    which are always present and give us at least the username and follower counts.

    Args:
        url:   Instagram profile URL.
        proxy: Optional proxy URL.

    Returns:
        Normalised profile dict (possibly with limited fields), or {} on failure.
    """
    username = url.rstrip("/").split("/")[-1].lstrip("@").split("?")[0]

    try:
        with httpx.Client(
            headers={
                "User-Agent": _IG_HEADERS["User-Agent"],
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
                # Referer: google.com makes the request look like a user arriving from a search.
                "Referer": "https://www.google.com/",
            },
            follow_redirects=True,
            timeout=15,
            proxies=proxy,
        ) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return {}

            html = resp.text
            # Try three known JS variable patterns that contain full profile JSON.
            patterns = [
                r'window\.__additionalDataLoaded\s*\(\s*["\']profile["\'],\s*(\{.+?\})\s*\)',
                r'"ProfilePage"\s*:\s*\[(\{.+?\})\]',
                r'window\._sharedData\s*=\s*(\{.+?\})\s*;',
            ]
            for pat in patterns:
                m = re.search(pat, html, re.DOTALL)
                if m:
                    try:
                        import json
                        raw = json.loads(m.group(1))
                        # Walk the nested structure: the user object lives at different
                        # depths depending on which variable was matched.
                        user = (
                            raw.get("graphql", {}).get("user")
                            or raw.get("entry_data", {}).get("ProfilePage", [{}])[0].get("graphql", {}).get("user")
                            or raw.get("user")
                            or {}
                        )
                        if user:
                            return _parse_ig_user_data(user, url)
                    except Exception:
                        continue

            # JSON blob not found — fall back to Open Graph meta tags.
            # These are always in the HTML and give us at least username + bio.
            soup = BeautifulSoup(html, "html.parser")

            def get_meta(prop: str, attr: str = "property") -> str:
                tag = soup.find("meta", {attr: prop})
                return (tag.get("content") or "").strip() if tag else ""

            og_title = get_meta("og:title")
            og_desc = get_meta("og:description")
            og_image = get_meta("og:image")

            # og:description format: "123K Followers, 456 Following, 789 Posts — ..."
            # Use regex to extract the numeric stats from the description string.
            followers = following = posts_count = ""
            if og_desc:
                nums = re.findall(r"([\d,\.]+[KMkm]?)\s+(\w+)", og_desc)
                for val, label in nums:
                    lbl = label.lower()
                    if "follower" in lbl: followers = val
                    elif "following" in lbl: following = val
                    elif "post" in lbl: posts_count = val

            # og:title format: "Display Name (@username) • Instagram photos and videos"
            display_name = ""
            if og_title:
                m2 = re.match(r"^(.+?)\s*\(", og_title)
                display_name = m2.group(1).strip() if m2 else og_title.replace("• Instagram", "").strip()

            if username:
                return {
                    "platform": "Instagram",
                    "url": url,
                    "username": username,
                    "full_name": display_name,
                    "bio": og_desc[:200] if og_desc else "",
                    "avatar": og_image,
                    "followers": followers,
                    "following": following,
                    "posts_count": posts_count,
                    "is_verified": False,
                    "is_private": False,
                    "external_url": "",
                    "latest_posts": [],
                    "type": "Profile",
                    "source": "meta-tags",
                }
    except Exception:
        pass
    return {}


def _scrape_instagram_browser(url: str, proxy: str | None) -> dict:
    """Strategy 3: Playwright browser with full network response interception.

    This is the most capable but slowest Instagram strategy.  It launches a
    real headless Chromium browser and attaches a response listener that
    captures every network response while the page loads.  When Instagram's
    JavaScript makes its internal API calls (web_profile_info, graphql/query),
    the listener extracts the user object and post edges from the JSON payloads.

    Key techniques:
      - page.on("response", handle_response): hooks into Playwright's network
        layer to receive every HTTP response the page makes — including XHR/fetch
        calls that are invisible to plain httpx.
      - navigator.webdriver is removed via add_init_script to suppress the most
        common Playwright fingerprint.
      - The page is scrolled halfway after load to trigger lazy-loaded post data,
        which Instagram fetches only when the user scrolls down.

    Uses sync_playwright (synchronous) rather than async because this function
    runs inside a ThreadPoolExecutor thread (see scrape_batch), not inside an
    asyncio event loop.

    Args:
        url:   Instagram profile URL.
        proxy: Optional proxy URL.

    Returns:
        Normalised profile dict, or {} if nothing was captured.
        Returns {"error": ..., "url": ...} on exception.
    """
    try:
        captured_user: dict = {}
        captured_posts: list = []

        with sync_playwright() as p:
            launch_options: dict = {
                "headless": config.BROWSER_HEADLESS,
                # Remove the AutomationControlled flag that Chrome normally sets
                # for WebDriver sessions — Instagram checks for this.
                "args": ["--disable-blink-features=AutomationControlled"],
            }
            if proxy:
                launch_options["proxy"] = {"server": proxy}

            browser = p.chromium.launch(**launch_options)
            context = browser.new_context(
                user_agent=_IG_HEADERS["User-Agent"],
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )
            # Patch navigator.webdriver and inject the chrome object that real
            # Chrome pages expect to exist (some anti-bot checks look for it).
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """)

            page = context.new_page()

            def handle_response(response):
                """Intercept and parse every network response the page receives."""
                nonlocal captured_user, captured_posts
                url_r = response.url
                try:
                    import json as _json
                    # Profile info endpoint — gives us the full user object.
                    if "web_profile_info" in url_r:
                        body = response.json()
                        user = (
                            body.get("data", {}).get("user")
                            or body.get("graphql", {}).get("user")
                            or {}
                        )
                        # Only capture the first valid user object found.
                        if user and user.get("username") and not captured_user:
                            captured_user = user

                    # GQL timeline or feed API — gives us post edges/items.
                    elif "graphql/query" in url_r or "api/v1/feed/user" in url_r:
                        body = response.json()
                        # Old GQL format: edges array nested inside user object.
                        edges = (
                            body.get("data", {}).get("user", {}).get("edge_owner_to_timeline_media", {}).get("edges", [])
                            or body.get("graphql", {}).get("user", {}).get("edge_owner_to_timeline_media", {}).get("edges", [])
                        )
                        if edges:
                            captured_posts.extend(edges)
                        # New format: flat items array (Reels / feed v2).
                        items = body.get("items", [])
                        if items:
                            # Wrap items in edge/node structure for uniform parsing.
                            captured_posts.extend([{"node": item} for item in items])
                except Exception:
                    pass

            # Register the listener before navigating so no early responses are missed.
            page.on("response", handle_response)
            page.goto(url, wait_until="networkidle", timeout=30000)
            # Extra wait to allow deferred API calls to complete after initial render.
            page.wait_for_timeout(3000)

            # Scroll to trigger lazy-loaded post data (Instagram fetches posts
            # only after the user scrolls below the fold).
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            page.wait_for_timeout(2000)

            browser.close()

        if captured_user:
            return _parse_ig_user_data(captured_user, url, extra_posts=captured_posts or None)

        return {}

    except Exception as e:
        return {"error": str(e), "url": url}


def _scrape_instagram_sync(url: str, proxy: str | None) -> dict:
    """Orchestrate the three Instagram strategies in order, returning the first success.

    Tries the fastest/cheapest strategy first (unofficial API) and escalates
    to the more expensive browser strategy only if the lighter ones fail.

    Args:
        url:   Instagram profile URL.
        proxy: Optional proxy URL.

    Returns:
        Normalised profile dict with a "source" key indicating which strategy
        succeeded, or an error dict if all three strategies failed.
    """
    # Strategy 1: Unofficial API (fastest — one HTTP round-trip after cookie grab).
    result = _scrape_instagram_api(url, proxy)
    if result and result.get("username"):
        result["source"] = "Instagram API"
        return result

    # Strategy 2: Embedded JSON / meta tags (medium — one HTTP round-trip).
    result = _scrape_instagram_json_embed(url, proxy)
    if result and result.get("username"):
        if "source" not in result:
            result["source"] = "Page Source"
        return result

    # Strategy 3: Headless browser (slowest — full browser launch + render).
    result = _scrape_instagram_browser(url, proxy)
    if result and result.get("username"):
        result["source"] = "Browser Intercept"
        return result

    return {"error": "Instagram profile could not be scraped. Profile may be private.", "url": url}


# ------------------------------------------------------------------
# Main dispatch
# ------------------------------------------------------------------

def _scrape_sync(url: str, proxy: str | None) -> dict:
    """Route a URL to the correct platform scraper based on domain.

    This is the function submitted to the ThreadPoolExecutor by scrape_batch.
    It runs synchronously so it is safe to call from a thread.

    Args:
        url:   Social-media profile URL (LinkedIn or Instagram).
        proxy: Optional proxy URL.

    Returns:
        Platform-specific profile dict, or an error dict for unsupported URLs.
    """
    if "linkedin.com" in url:
        result = _scrape_linkedin_via_google(url, proxy)
        if result and "error" not in result:
            return result
        # Return a user-friendly error explaining the limitation.
        return {
            "error": "LinkedIn requires authentication or was rate-limited by Google. Try again or use a proxy.",
            "url": url,
            "platform": "LinkedIn",
        }

    elif "instagram.com" in url:
        return _scrape_instagram_sync(url, proxy)

    return {"error": "Unsupported platform or URL", "url": url}


class SocialScraper:
    """Public async interface for scraping social-media profiles.

    This is the class imported and called by app/services/scraping_service.py.
    It wraps the synchronous scraping functions in an asyncio-compatible API
    by delegating to a ThreadPoolExecutor, which allows the FastAPI event loop
    to remain responsive while scraping happens in background threads.

    Args:
        proxy: Optional proxy URL forwarded to all scraping strategies.
    """

    def __init__(self, proxy: str | None = None):
        self.proxy = proxy

    async def scrape_batch(self, urls: list[str]) -> list[dict]:
        """Scrape a list of social-media profile URLs concurrently.

        Each URL is processed in a separate thread from _executor so multiple
        profiles can be scraped in parallel.  asyncio.gather waits for all
        threads to complete before returning.

        Args:
            urls: List of LinkedIn or Instagram profile URLs.

        Returns:
            List of profile dicts (or error dicts), one per input URL,
            in the same order as the input list.
        """
        loop = asyncio.get_event_loop()
        # run_in_executor submits _scrape_sync to the thread pool and returns
        # a coroutine that resolves when the thread completes.
        tasks = [
            loop.run_in_executor(_executor, _scrape_sync, url, self.proxy)
            for url in urls
        ]
        return list(await asyncio.gather(*tasks))
