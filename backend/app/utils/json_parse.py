"""Robust JSON parsing for LLM responses.

LLM output — especially from reasoning models — can arrive wrapped in markdown
code fences or with leading/trailing prose. This helper extracts and parses the
JSON object, raising a clear error when nothing usable is found.

Typical failure modes handled:
  1. Response wrapped in ```json ... ``` — stripped by ``_FENCE_RE``.
  2. Extra prose before/after the JSON object — handled by ``_extract_json_object``.
  3. Completely empty response — raised as ValueError immediately.
  4. Valid JSON but not a dict (e.g. a list) — raised as ValueError.
"""

from __future__ import annotations

import json
import re

# Matches opening ``` or ```json and closing ``` (handles optional whitespace).
_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def parse_llm_json(raw: str) -> dict:
    """Parse a JSON object out of an LLM response.

    Strips markdown code fences and surrounding whitespace. If the response
    has extra prose around the JSON, falls back to extracting the first
    balanced ``{...}`` span.

    Raises:
        ValueError: if the input is empty or no valid JSON object is found.
    """
    if not raw or not raw.strip():
        raise ValueError("LLM returned an empty response")

    # Strip ```json ... ``` fences if present; _FENCE_RE handles both
    # the opening tag (with or without "json") and the closing ```.
    text = _FENCE_RE.sub("", raw.strip()).strip()

    try:
        # Fast path: the cleaned text is already valid JSON.
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Slow path: extract the first balanced {...} span from surrounding prose.
        span = _extract_json_object(text)
        if span is None:
            raise ValueError(
                f"LLM response is not valid JSON (first 200 chars): {text[:200]!r}"
            )
        parsed = json.loads(span)

    # Agents always expect a dict; guard against LLMs returning arrays or scalars.
    if not isinstance(parsed, dict):
        raise ValueError(f"LLM JSON is not an object, got {type(parsed).__name__}")
    return parsed


def _extract_json_object(text: str) -> str | None:
    """Return the first balanced ``{...}`` substring, or None if absent.

    Walks the string character-by-character, tracking brace depth and string
    state (with escape awareness) so it correctly ignores ``{`` / ``}`` that
    appear inside string values rather than as structural JSON characters.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False          # previous backslash consumed; next char is literal
            elif ch == "\\":
                escape = True           # next char is escaped — don't treat it as structural
            elif ch == '"':
                in_str = False          # closing quote — exit string mode
        elif ch == '"':
            in_str = True               # opening quote — enter string mode
        elif ch == "{":
            depth += 1                  # nested object opens
        elif ch == "}":
            depth -= 1
            if depth == 0:
                # depth back to zero — we've found the matching closing brace
                return text[start : i + 1]
    return None
