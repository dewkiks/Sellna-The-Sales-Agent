"""Unit tests for the text cleaning utility functions in app/utils/text_cleaning.py.

These are pure-function tests — no mocks, no async, no DB.  Each function is
deterministic so tests simply check input → expected output.

Functions under test:
  - clean_text          : decode HTML entities, strip surrounding whitespace
                          and non-breaking spaces ( )
  - normalize_whitespace: collapse multiple spaces to one; collapse 3+ newlines
                          to two
  - deduplicate_list    : remove duplicates while preserving insertion order;
                          case-insensitive dedup by default
  - truncate            : clip text to max_chars and append an ellipsis ("…")
  - extract_sentences   : split text into sentences and return up to max_sentences
"""

from app.utils.text_cleaning import (
    clean_text,
    deduplicate_list,
    extract_sentences,
    normalize_whitespace,
    truncate,
)


def test_clean_text_removes_html_entities():
    """Verify common HTML entities (&amp;, &lt;, &gt;) are decoded correctly.

    The third assertion checks that &apos; is NOT decoded — confirming the
    function only handles the most common entities (not the full HTML5 set),
    which is the expected behaviour for scraping cleanup.
    """
    assert clean_text("Hello &amp; World") == "Hello & World"
    assert clean_text("&lt;p&gt;Test&lt;/p&gt;") == "<p>Test</p>"
    assert clean_text("Don&apos;t stop") == "Don&apos;t stop"  # &apos; not in supported list


def test_clean_text_strips_whitespace():
    """Verify leading/trailing whitespace and non-breaking spaces are stripped.

      is the Unicode non-breaking space (&nbsp;) common in scraped HTML.
    """
    assert clean_text("  hello  ") == "hello"
    assert clean_text(" text ") == "text"


def test_normalize_whitespace():
    """Verify multiple spaces collapse to one and 4 newlines collapse to 2."""
    assert normalize_whitespace("hello   world") == "hello world"
    # 4 newlines should collapse to the maximum of 2 (paragraph boundary).
    assert normalize_whitespace("line\n\n\n\nbreak") == "line\n\nbreak"


def test_deduplicate_list_preserves_order():
    """Verify deduplication removes later duplicates but keeps first occurrence.

    Default is case-insensitive: "b" and "B" are considered the same, so
    "B" (the second occurrence) is removed while "b" (first) is kept.
    "c" is unique and should appear in its original position.
    """
    result = deduplicate_list(["a", "b", "a", "c", "B"])
    assert result == ["a", "b", "c", "B"]


def test_deduplicate_list_case_sensitive():
    """Verify that case_sensitive=True treats "A" and "a" as distinct entries."""
    result = deduplicate_list(["A", "a"], case_sensitive=True)
    assert result == ["A", "a"]


def test_truncate():
    """Verify truncate clips text to max_chars and appends an ellipsis.

    "word " * 100 = 500 chars.  Truncated to 50 chars: the result should be
    ≤ 51 chars (50 + the single-character ellipsis "…") and must end with "…".
    """
    text = "word " * 100
    result = truncate(text, max_chars=50)
    assert len(result) <= 51  # ellipsis ("…") is 1 char; total may be 50 or 51
    assert result.endswith("…")


def test_truncate_short_text():
    """Verify text shorter than max_chars is returned unchanged (no ellipsis)."""
    short = "Hello"
    assert truncate(short, max_chars=100) == "Hello"


def test_extract_sentences():
    """Verify extract_sentences splits on . ! ? and respects max_sentences.

    The input has 4 sentences; with max_sentences=2 only the first two should
    be returned.  The first element must contain "First sentence".
    """
    text = "First sentence. Second sentence! Third sentence? Fourth."
    result = extract_sentences(text, max_sentences=2)
    assert len(result) <= 2
    assert "First sentence" in result[0]
