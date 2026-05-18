"""Playwright browser-fingerprint masking utilities (stealth patches).

Modern websites detect headless browsers by checking for telltale JavaScript
properties that Playwright sets differently from a real Chrome browser.
This module applies patches that make the Playwright-controlled browser look
as close as possible to a genuine user's browser session.

When is this used?
  scraper.py calls apply_stealth() on every Playwright page before navigating,
  specifically in _fetch_js().  This covers the JS-render fallback path used
  when httpx is blocked by a site's bot detection.

What does playwright_stealth do?
  The playwright-stealth library patches dozens of browser properties in one
  call, including:
    - navigator.webdriver        (set to true by WebDriver-based automation)
    - navigator.plugins          (empty in headless Chrome, non-empty in real Chrome)
    - navigator.languages        (missing or wrong in automation contexts)
    - window.chrome              (absent in headless Chrome, present in real Chrome)
    - screen dimensions and color depth
    - WebGL renderer strings     (headless Chrome uses a generic "SwiftShader" GPU)
    - hairlineFeature, permissions API behaviour
    - and more — the full list is in the playwright-stealth source.

The additional manual patch below (navigator.webdriver = undefined) is a
belt-and-suspenders measure in case the stealth library's coverage is
incomplete for the installed version.
"""

from playwright.async_api import Page
from playwright_stealth import Stealth


async def apply_stealth(page: Page) -> None:
    """Apply browser-fingerprint masking to a Playwright page before navigation.

    Must be called after page creation but BEFORE page.goto(), because the
    patches are injected as init scripts that run at document creation time.
    Calling it after navigation would be too late — the bot-detection check
    may have already run.

    Two layers of masking are applied:
      1. Stealth().apply_stealth_async(page) — the playwright-stealth library
         patches the full set of known fingerprinting vectors automatically.
      2. A manual add_init_script that explicitly sets navigator.webdriver to
         undefined.  This property is the single most commonly checked signal
         because WebDriver sets it to true, while real browsers leave it absent.

    Args:
        page: A Playwright Page object that has NOT yet navigated to any URL.
    """
    # Layer 1: playwright-stealth comprehensive fingerprint masking.
    await Stealth().apply_stealth_async(page)

    # Layer 2: Belt-and-suspenders patch for navigator.webdriver.
    # Object.defineProperty with a getter returning undefined means:
    #   - The property exists (some checks do `'webdriver' in navigator`)
    #   - But its value is undefined, not true (passes the `!navigator.webdriver` check)
    # This is necessary because some sites check for webdriver even after
    # playwright-stealth has run, using more sophisticated detection scripts.
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)
