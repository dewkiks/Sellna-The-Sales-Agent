# app/services — Shared Infrastructure Services

## Purpose

The `services` package provides four cross-cutting capabilities that every
agent in the Sellna.ai pipeline depends on.  No agent talks directly to the
LLM API, the vector database, or the web scraper — instead it calls one of
these services, keeping agent code focused on business logic rather than
infrastructure concerns.

All long-lived objects (LLM client, embedding model, vector store connection)
are constructed exactly **once** per process via `lru_cache(maxsize=1)` factory
functions (e.g. `get_llm_service()`), then shared across concurrent coroutines.

---

## Files

| File | One-line description |
|---|---|
| `__init__.py` | Package marker; documents the four service modules. |
| `llm_service.py` | Provider-agnostic async LLM client. Reads `LLM_PROVIDER` from `.env` and routes all chat calls through the OpenAI Python SDK regardless of which backend is active (Groq, Grok, OpenRouter, NVIDIA, Ollama, …). Supports streaming (SSE token callbacks) and retries on HTTP 429. |
| `embedding_service.py` | Converts text strings to dense float vectors. Uses OpenAI `text-embedding-3-small` when `LLM_PROVIDER=openai`, and falls back automatically to local `SentenceTransformers` (`all-MiniLM-L6-v2`) for all other providers (including Groq/Grok which have no embedding API). |
| `rag_service.py` | Three-step Retrieval-Augmented Generation pipeline: **index** (embed + upsert to Qdrant), **retrieve** (embed query + cosine similarity search), **generate** (inject retrieved chunks into LLM prompt). Used by GapAnalysisAgent, PersonaAgent, and OutreachAgent. |
| `scraping_service.py` | High-level async scraper adapter. Wraps the root-level `scrapping_module` (httpx + Playwright engine + social scrapers) so agents do not know the underlying implementation. Provides `scrape_websites()`, `scrape_social()`, and `scrape_competitor_homepage()`. |

---

## How this folder fits the overall architecture

```
FastAPI routes
    └── SalesPipeline (app/pipelines/)
            └── Agents (app/agents/)
                    ├── LLMService      ← every agent
                    ├── EmbeddingService ← RAGService internally
                    ├── RAGService      ← GapAnalysisAgent, PersonaAgent, OutreachAgent
                    └── ScrapingService ← WebAgent, SocialAgent
                            └── scrapping_module (project root)
                                    ├── scraper.Scraper
                                    ├── extractor.extract()
                                    └── scrapping_module.social.SocialScraper
```

`LLMService` and `EmbeddingService` are singletons (one per process).
`RAGService` is instantiated per agent call but its three dependencies
(`vector_store`, `embedding_service`, `llm_service`) are the shared singletons.
`ScrapingService` is instantiated per pipeline run (proxy/render_js may differ).

---

## Likely exam questions

**Q1. What is Retrieval-Augmented Generation (RAG) and which agents use it?**

RAG is a three-step pattern: (1) *Index* — embed documents and store vectors
in Qdrant; (2) *Retrieve* — embed the query, run cosine similarity search, get
the top-k most relevant text chunks; (3) *Generate* — inject the chunks as
context into the LLM prompt so the answer is grounded in real data rather than
hallucinated.  In Sellna.ai, GapAnalysisAgent, PersonaAgent, and OutreachAgent
all use `RAGService` — they index cleaned competitor data then retrieve it
before generating their respective outputs.

**Q2. Why does EmbeddingService offload SentenceTransformer.encode() to a thread pool?**

`SentenceTransformer.encode()` is a synchronous, CPU-bound function (matrix
multiplications on a PyTorch model).  Calling it directly inside an `async`
function would block the asyncio event loop, freezing all other concurrent
pipeline coroutines until the encoding finishes.  `loop.run_in_executor(None, ...)`
runs it in the default thread pool, keeping the event loop free.

**Q3. How does LLMService support so many different providers without changing code?**

All supported providers (Groq, Grok, OpenAI, OpenRouter, NVIDIA, Ollama, …)
offer an OpenAI-compatible REST API.  `LLMService` constructs a single
`AsyncOpenAI` client and sets only `base_url` and `api_key` from `.env`.
Switching providers requires only changing `LLM_PROVIDER` (and the matching
API key) in `.env` — no code changes needed.

**Q4. What happens when the LLM returns HTTP 429 (rate limit)?**

`LLMService.chat()` loops up to 4 attempts.  On each 429 it waits an
exponentially increasing delay (3 s, 6 s, 12 s) using `asyncio.sleep` before
retrying.  Any non-rate-limit exception or exhaustion of retries propagates to
the caller.

**Q5. How does streaming output reach the frontend?**

`LLMService.chat()` accepts an `on_token` callback.  When provided, the request
uses `stream=True` and each content delta fires `on_token(text)`.  The pipeline
passes down a `stream_cb` that wraps this in SSE-compatible event dicts (tagged
with the agent name via `_make_agent_cb`) which the FastAPI route pushes over
Server-Sent Events to the React frontend.

**Q6. Why does scraping_service.py manipulate sys.path?**

`scrapping_module` (and `scraper`, `extractor`) live at the project root, not
inside `app/`.  They are not installed as pip packages.  To make them importable
from both the FastAPI process and any Celery worker process, `scraping_service`
adds the project root to `sys.path` at import time (only once, guarded by an
`if project_root not in sys.path` check).

**Q7. What does score_threshold do in RAGService.retrieve()?**

It is a minimum cosine similarity (default 0.3 on a 0–1 scale).  Qdrant points
below this threshold are discarded even if they are in the top-k results.  This
prevents injecting weakly related chunks into the LLM context, which could
confuse the model or dilute relevant information.
