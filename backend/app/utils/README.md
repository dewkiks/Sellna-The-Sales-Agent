# app/utils — Shared Helper Utilities

The `utils` package contains small, stateless helper modules that are used
across multiple agents and services.  All functions here are pure (no I/O,
no database access) and have no dependencies on other application modules,
making them easy to unit-test in isolation.

## Files

| File | Description |
|---|---|
| `__init__.py` | Package marker with brief module summary. |
| `json_parse.py` | Extracts and parses a JSON object from raw LLM output, handling markdown fences and surrounding prose. |
| `similarity.py` | Pure-Python cosine similarity and top-k ranking for embedding vectors. |
| `text_cleaning.py` | HTML entity decoding, control-character removal, whitespace normalisation, deduplication, truncation, and sentence splitting for scraped web content. |

## Architecture fit

These utilities sit at the lowest level of the stack — they have no imports
from `app.db`, `app.agents`, or `app.services`, and are safe to call from
anywhere:

```
Any agent / service
        |
        v
   app/utils/json_parse.py    <-- parse LLM JSON responses
   app/utils/text_cleaning.py <-- clean scraped web text before embedding
   app/utils/similarity.py    <-- quick in-process vector ranking
```

**`json_parse.py`** is called immediately after every LLM response to turn
raw text into a Python dict.  Robustness is critical here: LLMs frequently
wrap JSON in markdown fences or add explanatory prose, and a parsing failure
would stall the entire pipeline stage.

**`text_cleaning.py`** is called by the Web Agent and Cleaning Agent before
content is sent to the LLM or embedded into the vector store.  Cleaner text
means shorter prompts and better embedding quality.

**`similarity.py`** provides a CPU-only fallback for ranking embeddings when
neither Qdrant nor FAISS is involved (e.g. small candidate sets computed
entirely in-process).

## Likely exam questions

**Q: How does `parse_llm_json` handle a response that has prose before and after the JSON?**
A: It first strips markdown code fences with a regex. If the result still fails `json.loads`, it calls `_extract_json_object`, which walks the string character-by-character tracking brace depth and string state to find the first balanced `{...}` span — then parses only that span.

**Q: Why does `_extract_json_object` track `in_str` and `escape` state?**
A: Braces inside JSON string values (e.g. `"description": "revenue grew by {20%}"`) must not be counted as structural braces. The `in_str` flag suppresses depth counting while inside a quoted string; the `escape` flag prevents a `\"` from being misread as the closing quote.

**Q: What is cosine similarity and what does a value of 1.0 mean?**
A: Cosine similarity measures the angle between two vectors: `cos(θ) = (A·B) / (||A|| * ||B||)`. A value of 1.0 means the vectors point in exactly the same direction (identical semantic content). 0.0 means orthogonal (unrelated). Most embedding models produce unit-length vectors, so cosine similarity equals the dot product.

**Q: Why does `deduplicate_list` use a `seen` set rather than `list(set(items))`?**
A: `set()` does not preserve insertion order. The `seen` set approach retains the original order of first occurrence, which matters when the agent output list is ranked (e.g. most important features first).

**Q: Why does `truncate` use `rsplit(" ", 1)` instead of a plain slice?**
A: A plain slice `text[:500]` can cut mid-word, producing garbled output. `rsplit(" ", 1)` finds the last word boundary before the limit, so the truncated text ends on a complete word before the ellipsis.

**Q: How is `text_cleaning.py` different from Python's built-in `str.strip()`?**
A: `str.strip()` only removes leading/trailing whitespace. `clean_text` additionally decodes HTML entities (`&amp;`, `&nbsp;`, etc.), removes invisible Unicode characters (zero-width spaces, BOM), and strips C0 control characters — artefacts that appear in scraped web content and would corrupt LLM tokenisation.
