# app/pipelines — Sales Intelligence Pipeline Orchestrator

## Purpose

The `pipelines` package contains the single top-level orchestrator,
`SalesPipeline`, that sequences all nine AI agent stages into one coherent
end-to-end workflow.  It receives a `CompanyInput` (domain + company name
from the user), drives every agent in order, persists results to PostgreSQL
after each stage, and returns a `PipelineResult` containing competitors,
market gaps, ICPs, buyer personas, and personalised outreach copy.

---

## Files

| File | One-line description |
|---|---|
| `__init__.py` | Exports `SalesPipeline` and `PipelineResult` for the FastAPI route layer. |
| `sales_pipeline.py` | The 9-stage async orchestrator: instantiates agents, manages parallelism (scraping / persona / outreach run concurrently), handles timeouts, persists to the DB, and fires SSE streaming callbacks to the frontend. |

---

## How this folder fits the overall architecture

```
HTTP POST /api/v1/pipeline/run
    │
    ▼
app/api/v1/pipeline.py      ← FastAPI route injects DB session + builds callbacks
    │
    ▼
SalesPipeline.run()         ← THE orchestrator (this folder)
    │
    ├── Stage 1  DomainAgent           (app/agents/)   uses LLMService
    ├── Stage 2  CompetitorAgent        (app/agents/)   uses LLMService
    ├── Stage 3  WebAgent               (app/agents/)   uses ScrapingService
    ├── Stage 3.5 SocialAgent           (app/agents/)   uses ScrapingService (social)
    ├── Stage 4  CleaningAgent          (app/agents/)   uses LLMService
    ├── Stage 5  GapAnalysisAgent       (app/agents/)   uses RAGService
    ├── Stage 6  ICPAgent               (app/agents/)   uses LLMService
    ├── Stage 7  PersonaAgent           (app/agents/)   uses RAGService
    └── Stage 8  OutreachAgent          (app/agents/)   uses RAGService
            │
            ▼
    app/db/repositories.py   ← PostgreSQL persistence after every stage
```

The pipeline is the *only* place that knows about stage ordering, parallelism
strategy, and persistence.  Each agent is stateless and knows only its own
input/output schema.

---

## Likely exam questions

**Q1. Walk me through the 9 pipeline stages — what does each one do?**

1. **DomainAgent** — analyses the company's domain with LLM + SERP data to
   produce a `CompanyAnalysis` (industry, value prop, target market, …).
2. **CompetitorAgent** — asks the LLM to identify up to N direct competitors
   based on the company analysis; returns `[CompetitorDiscovered]`.
3. **WebAgent** — scrapes each competitor's homepage using `ScrapingService`
   (httpx + optional Playwright); returns `[CompetitorWebData]`.
4. **SocialAgent** — discovers and scrapes LinkedIn/Instagram accounts for the
   company and each competitor; returns `[SubjectSocials]`.
5. **CleaningAgent** — uses the LLM to normalise raw web data into structured
   `[CompetitorCleanData]` profiles (features, pricing, positioning, …).
6. **GapAnalysisAgent** — indexes cleaned profiles in Qdrant (RAG), retrieves
   the most relevant chunks, then asks the LLM to identify `[MarketGap]`
   opportunities the subject company could exploit.
7. **ICPAgent** — generates `[ICPProfile]` (Ideal Customer Profile) objects
   describing the firmographic and psychographic traits of the best-fit buyers.
8. **PersonaAgent** — for each ICP, retrieves gap context via RAG and generates
   detailed `[BuyerPersona]` objects (job title, pain points, goals, …).
9. **OutreachAgent** — for each persona, retrieves persona + gap context via RAG
   and writes personalised `[OutreachAsset]` copy (cold email, LinkedIn message,
   call script) tailored to that persona's pain points.

**Q2. Why do some stages run in parallel while others are sequential?**

Stages 3 (web scraping) and 3.5 (social scraping) are **I/O-bound** — each URL
fetch is independent and the bottleneck is network latency, not CPU.  Running
them concurrently with `asyncio.as_completed()` means results arrive and are
persisted as each URL finishes, so a single slow site does not delay the rest.
Stage 7 (persona) is parallel per ICP and Stage 8 (outreach) is parallel per
persona for the same reason — each persona/outreach call is an independent LLM
request.  Stages 1, 2, 4, 5, 6 are sequential because each depends on the full
output of the previous stage.

**Q3. What is the difference between asyncio.as_completed() and asyncio.gather() and where is each used?**

`asyncio.as_completed()` yields futures one by one as they complete.  The
pipeline uses this for web and social scraping (Stage 3 / 3.5) and persona
generation (Stage 7) because it allows partial results to be saved to the DB
incrementally — if one task fails, the others are still processed.
`asyncio.gather(*tasks, return_exceptions=True)` launches all tasks and waits
for **all** to finish, returning results (or exception objects) in the original
order.  The pipeline uses this for outreach generation (Stage 8) because it
needs all persona outreach results together; `return_exceptions=True` means a
single failure does not cancel other outreach tasks.

**Q4. What happens if a sequential stage times out or throws an exception?**

`_run_stage()` wraps every sequential stage in `asyncio.wait_for` (configurable
timeout from `settings.pipeline_timeout_seconds`).  On `TimeoutError` **or**
any `Exception` the error message is appended to `errors: list[str]` and `None`
is returned.  The calling code falls back to an empty list, so subsequent stages
receive no input and emit a `warnings` entry rather than crashing.  The full
`PipelineResult` is still returned at the end — callers check `result.errors`
and `result.warnings` to understand what failed.

**Q5. How does live progress reach the frontend during a run?**

The pipeline receives two optional callbacks at construction time:

- `on_progress(status, progress, company_id)` — fires coarse integer percentage
  updates (10 % per stage) used by an HTTP polling endpoint.
- `stream_cb(event: dict)` — fires fine-grained typed events
  (`agent_start`, `scrape_tick`, `agent_done`, `done`).

`_make_agent_cb(agent_name)` wraps `stream_cb` so each agent's events are
tagged with their agent name (e.g. `"agent": "WebAgent"`).  The FastAPI route
pushes these dicts to the browser over Server-Sent Events (SSE), letting the
React frontend render per-agent thinking panels in real time.

**Q6. Why are competitor IDs realigned after bulk_create?**

`CompetitorAgent` assigns a temporary in-memory UUID to each `CompetitorDiscovered`
object.  `bulk_create` inserts the rows into PostgreSQL, which generates its own
IDs (auto-increment or DB-side UUID).  If the in-memory IDs were used in later
`update_web_data()` / `update_clean_data()` calls, they would match no DB row
and the scraped data would silently be lost.  The pipeline therefore iterates
`zip(competitors, created)` and overwrites each object's `competitor_id` with the
actual DB-assigned ID before proceeding.

**Q7. How are RAG collections scoped per company?**

The collection name is derived from the company's DB ID:
`rag_collection = f"gap_{company_id}"`.  Because every pipeline run uses a
unique company ID, each run gets its own isolated Qdrant collection.  This
prevents data from one company's competitor profiles from appearing in another
company's retrieval results.
