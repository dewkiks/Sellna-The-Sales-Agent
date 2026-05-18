"""Text cleaning utilities shared across agents.

These functions are applied to raw web-scraped content before it is fed to
LLMs or embedded into the vector store.  Cleaner input means shorter prompts,
fewer tokenisation artefacts, and better embedding quality.
"""

from __future__ import annotations

import re


def clean_text(text: str) -> str:
    """Remove excess whitespace, stray HTML entities, and control chars.

    BeautifulSoup handles most HTML entity conversion, but some entities
    (notably ``&nbsp;`` and zero-width Unicode characters) slip through \u2014
    this function catches the common residuals.

    Unicode zero-width characters (\u200b, \u200c, \u200d) are invisible
    but corrupt tokenisation; the BOM (\ufeff) is stripped for the same reason.
    """
    if not text:
        return ""
    # Decode common HTML entities that bs4 didn't convert
    replacements = {
        "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&quot;": '"', "&#39;": "'", "&nbsp;": " ",
        "\u00a0": " ",   # non-breaking space \u2192 regular space
        "\u200b": "",    # zero-width space \u2014 invisible, breaks tokenisation
        "\u200c": "",    # zero-width non-joiner
        "\u200d": "",    # zero-width joiner
        "\ufeff": "",    # byte-order mark (BOM)
    }
    for entity, char in replacements.items():
        text = text.replace(entity, char)

    # Strip C0 control characters (except \t=\x09 and \n=\x0a, which are whitespace).
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text.strip()


def normalize_whitespace(text: str) -> str:
    """Collapse multiple spaces/newlines into single space or double newline.

    Runs of 3+ newlines become 2 (paragraph break preserved); runs of
    spaces/tabs become a single space.  Called after ``clean_text`` to produce
    a compact, embed-friendly string.
    """
    text = re.sub(r"[ \t]+", " ", text)       # multiple spaces/tabs → single space
    text = re.sub(r"\n{3,}", "\n\n", text)     # 3+ newlines → paragraph break
    return text.strip()


def deduplicate_list(items: list[str], case_sensitive: bool = False) -> list[str]:
    """Return list with duplicates removed, preserving original order.

    Order-preserving deduplication via a ``seen`` set.  By default comparison
    is case-insensitive (keeps the first casing encountered) so that
    "Salesforce" and "salesforce" are treated as the same feature.
    """
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item if case_sensitive else item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)  # keep the original-cased string in output
    return result


def truncate(text: str, max_chars: int = 500) -> str:
    """Truncate text to a maximum character length without mid-word cuts.

    Uses ``rsplit(" ", 1)`` to break at the last space boundary before the
    limit, then appends "…" so the output is clearly an excerpt.
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"


def extract_sentences(text: str, max_sentences: int = 5) -> list[str]:
    """Split text into sentences and return up to max_sentences.

    Splits on terminal punctuation (.!?) followed by whitespace.  Sentences
    shorter than 15 characters are filtered out (e.g. stray "OK." artefacts).
    """
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 15][:max_sentences]
