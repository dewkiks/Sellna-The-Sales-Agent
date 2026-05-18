# Sellna.ai — Backend Guide

> A study-oriented walkthrough of the **backend** of Sellna.ai. Read this top to
> bottom before your presentation — then dive into the per-folder `README.md`
> files for detail. Every backend `.py` file has been commented for study.

---

## 1. What the backend does

Sellna.ai is a **multi-agent B2B sales-intelligence platform**. A user submits a
company (name + domain + a few details). The backend then runs a **pipeline of 9
AI agents** that turns that single input into a full go-to-market intelligence
package:

```
Company input
   → competitor discovery + analysis
   → market-gap analysis
   → Ideal Customer Profiles (ICPs)
   → buyer personas
   → personalized outreach copy (cold email / LinkedIn / call opener)
```

The backend is a **FastAPI** application. It exposes a REST API that the React
frontend calls, runs the agent pipeline in the background, scrapes the web and
social media for raw intelligence, stores everything in PostgreSQL, and uses a
vector database for **RAG** (Retrieval-Augmented Generation).

---

## 2. Tech stack

| Concern | Technology | Where |
|---|---|---|
| Web framework | FastAPI (async) | `app/main.py`, `app/api/` |
| Database | PostgreSQL + SQLAlchemy 2.x (async ORM) | `app/db/postgres.py` |
| Vector database (RAG) | Qdrant (FAISS fallback) | `app/db/vector_store.py` |
| LLM | OpenAI-compatible client (OpenAI / Groq / Ollama) | `app/services/llm_service.py` |
| Embeddings | OpenAI or local SentenceTransformers | `app/services/embedding_service.py` |
| Web scraping | httpx + Playwright | `webscraper/` |
| Social scraping | Playwright + Google SERP technique | `scrapping_module/` |
| Background jobs | Celery + Redis (optional) | `app/workers/` |
| Config | Pydantic Settings (`.env`) | `app/config/settings.py` |
| Logging | structlog (JSON in prod) | `app/core/logging.py` |
| Auth | JWT (python-jose) | `app/core/security.py` |
| Live progress | Server-Sent Events (SSE) | `app/core/stream_manager.py` |
| Data contracts | Pydantic v2 models | `app/schemas/` |

---

## 3. Backend directory map

```
sellna.ai/                        ← repo root (monorepo)
│
├── frontend/                     ← Next.js app (separate — has its own README)
│
└── backend/                      ← ALL Python lives here; run commands from here
    │
    ├── main.py                   ← Dev runner — boots the FastAPI app on :8001
    ├── scraper_standalone.py     ← Standalone scraper-only FastAPI app (:8000)
    ├── pyproject.toml · uv.lock · requirements.txt · .env
    │
    ├── app/                      ← The FastAPI application package
    │   ├── main.py               ← App factory: CORS, middleware, routers, lifespan
    │   │
    │   ├── api/                  ← REST layer — HTTP endpoints the frontend calls
    │   │   ├── router.py         ← Mounts every v1 sub-router
    │   │   └── v1/               ← One module per feature (pipeline, company, icp …)
    │   │
    │   ├── agents/               ← The 9 AI agents (one job each) ★ core
    │   ├── pipelines/            ← Orchestrator that runs the agents in order ★ core
    │   ├── services/             ← Shared capabilities: LLM, embeddings, RAG, scraping ★ core
    │   │
    │   ├── db/                   ← Database layer
    │   │   ├── postgres.py       ← Async engine + ORM models
    │   │   ├── vector_store.py   ← Qdrant/FAISS abstraction (RAG storage)
    │   │   └── repositories/     ← Typed CRUD classes (one per entity)
    │   │
    │   ├── schemas/              ← Pydantic models — data contracts between agents
    │   ├── core/                 ← Cross-cutting: logging, security, DI, SSE manager
    │   ├── config/               ← Pydantic Settings loaded from .env
    │   ├── workers/              ← Celery app + background tasks
    │   └── utils/                ← Small pure helpers (json parsing, similarity …)
    │
    ├── webscraper/               ← Generic web-scraping engine ★ core
    │   ├── scraper.py            ← Fetch engine (httpx + Playwright)
    │   ├── extractor.py          ← Raw HTML → structured-data parser
    │   └── config.py             ← Scraper-engine config
    │
    ├── scrapping_module/         ← Social-media scraper (LinkedIn, Instagram) ★ core
    │   └── engines/              ← Per-platform engine classes (experimental)
    │
    ├── scripts/                  ← Manual dev/debug scripts (test_qdrant, verify_fix)
    ├── tests/                    ← pytest suite (in-memory SQLite, mocked LLM)
    ├── static/                   ← static assets served by the API
    └── docker/                   ← Dockerfile + docker-compose (full local stack)
```

★ = the modules your tutor is most likely to ask about. Each folder above has
its own `README.md` with a file table and **"Likely exam questions"**.

---

## 4. Architecture — how the layers fit together

The backend follows a **layered architecture**. A request flows down through the
layers; each layer has one responsibility and only talks to the layer below it.

```
   React frontend
        │  HTTP / JSON  +  SSE (live progress)
        ▼
┌──────────────────────────────────────────────┐
│  API layer            app/api/v1/*.py         │  validates input, returns JSON
├──────────────────────────────────────────────┤
│  Orchestration        app/pipelines/          │  runs the 9 agents in order
├──────────────────────────────────────────────┤
│  Agents               app/agents/             │  one reasoning step each
├──────────────────────────────────────────────┤
│  Services             app/services/           │  LLM · embeddings · RAG · scraping
├──────────────────────────────────────────────┤
│  Data layer           app/db/                 │  repositories → ORM → PostgreSQL
│                                                  vector store → Qdrant
└──────────────────────────────────────────────┘

Cross-cutting (used by every layer):  app/core/  ·  app/config/  ·  app/schemas/
```

**Key idea — data contracts.** Agents never pass raw dicts to each other. Each
agent returns a **Pydantic schema** (`app/schemas/`), and the next agent accepts
that schema. This makes the pipeline type-safe and easy to reason about.

---

## 5. The pipeline — the heart of the backend

`app/pipelines/sales_pipeline.py` runs **9 stages**. Each stage is one agent.

| # | Stage | Agent | What it does | Uses |
|---|---|---|---|---|
| 1 | Domain intelligence | `DomainAgent` | LLM analyses the company | LLM |
| 2 | Competitor discovery | `CompetitorAgent` | LLM lists real competitors | LLM |
| 3 | Web intelligence | `WebAgent` | Scrapes every competitor website | Scraper (parallel) |
| 4 | Social intelligence | `SocialAgent` | Finds social profiles + people | Social scraper (parallel) |
| 5 | Data cleaning | `CleaningAgent` | Normalises scraped text | — |
| 6 | Gap analysis | `GapAnalysisAgent` | Finds market positioning gaps | **RAG** |
| 7 | ICP generation | `ICPAgent` | Builds Ideal Customer Profiles | LLM |
| 8 | Persona generation | `PersonaAgent` | Builds buyer personas per ICP | **RAG** (parallel) |
| 9 | Outreach generation | `OutreachAgent` | Writes email / LinkedIn / call copy | **RAG** (parallel) |

**Why some stages run in parallel.** Scraping 10 competitor sites sequentially
would take minutes. Stages 3, 4 and 8 use `asyncio.as_completed` / `asyncio.gather`
to run their work concurrently and process each result as it arrives.

**Error handling.** `_run_stage()` wraps each stage in a timeout + try/except.
A failed stage is recorded in `errors[]` and the pipeline continues with whatever
data it has — one bad scrape never crashes the whole run.

**Live progress.** The pipeline emits events through a `stream_cb` callback.
Those events flow into `StreamManager` (`app/core/stream_manager.py`) and out to
the browser as **Server-Sent Events**, which is how the frontend shows the live
agent logs.

---

## 6. RAG — Retrieval-Augmented Generation

Stages 6, 8 and 9 use **RAG** (`app/services/rag_service.py`):

1. **Index** — scraped competitor text is split into chunks, converted to
   embedding vectors, and stored in the vector database (Qdrant).
2. **Retrieve** — for a question (e.g. "what gaps exist?"), the most similar
   chunks are fetched by vector similarity search.
3. **Generate** — those chunks are injected into the LLM prompt as context.

This grounds the LLM's answers in **real scraped evidence** instead of letting it
hallucinate, and keeps prompts small (only relevant chunks, not everything).

---

## 7. The two scraping subsystems

The user-facing emphasis ("webscraping, social scraping") maps to two distinct
pieces — keep them straight for your presentation:

| | Generic web scraper | Social scraper |
|---|---|---|
| Files | `webscraper/` (`scraper.py`, `extractor.py`, `config.py`) | `scrapping_module/` |
| Used by | `WebAgent` (stage 3) | `SocialAgent` (stage 4) |
| Target | Any competitor website | LinkedIn, Instagram profiles |
| How | httpx for static pages; **Playwright** when the page needs JavaScript | Playwright + a **Google-search technique** to find LinkedIn pages without LinkedIn's API |
| Anti-bot | Rotating user-agents, header spoofing, retry/backoff | `stealth.py` browser-fingerprint patches |

Both are reached from the app through `app/services/scraping_service.py`, which
is an **adapter** — it bridges the FastAPI app to the standalone scraper code so
the scraper stays decoupled from the app.

---

## 8. Running the backend

```powershell
# All backend commands run from the backend/ folder.
cd backend

# 1. Install (uv is used in this repo)
uv sync                     # or: pip install -r requirements.txt
playwright install chromium

# 2. Configure
Copy-Item .env.example .env # then fill in OPENAI/GROQ key + DATABASE_URL

# 3. Run the API (dev)
uv run python main.py       # → http://localhost:8001/docs

# 4. (optional) Background worker — only if you want Celery instead of the
#    built-in in-process fallback
uv run celery -A app.workers.celery_app worker --loglevel=info

# 5. Tests — no real DB or API key needed
uv run --extra dev pytest tests/ -v
```

If no Celery worker is running, `POST /pipeline/run` automatically falls back to
FastAPI `BackgroundTasks` and runs in-process — see `app/api/v1/pipeline.py`.

---

## 9. Is the backend organised "like professional coders do"?

**Short answer: yes — this is a genuinely well-structured backend.** It would
read as professional in a code review. Here is the honest breakdown.

### What is done right (say this confidently in your presentation)

- **Layered architecture with separation of concerns** — API / orchestration /
  agents / services / data are cleanly separated. Each file has one job.
- **Repository pattern** (`app/db/repositories/`) — database access is isolated
  behind typed CRUD classes, so route code never writes raw SQL.
- **Typed data contracts** — Pydantic schemas (`app/schemas/`) are passed between
  agents instead of loose dicts. This is exactly how production teams do it.
- **Dependency injection** — FastAPI `Depends()` supplies the DB session and
  settings, which makes the code testable.
- **Stateless agents** — every agent is created fresh per run and holds no state,
  so the pipeline is safe to run concurrently.
- **Configuration via environment** — no secrets hard-coded; `.env` + Pydantic
  Settings, with `@lru_cache` so settings load once.
- **Graceful degradation** — Celery→BackgroundTasks fallback, Qdrant→FAISS
  fallback, per-stage error capture. The system bends instead of breaking.
- **Cross-cutting concerns centralised** — logging, auth, and streaming live in
  `app/core/` rather than being scattered.
- **A test suite** that runs without external services (in-memory SQLite,
  mocked LLM).

### Honest nitpicks (a senior reviewer might mention these — good to acknowledge)

- **`scrapping_module/`** is spelled with a typo ("scrapping" → "scraping").
  A polished repo would fix the spelling. It is, however, cleanly decoupled
  from the app via `app/services/scraping_service.py`.
- **`app/db/repositories/`** keeps all repository classes in one `__init__.py`.
  Fine at this size; a larger codebase would split one file per entity.
- **`_LOCAL_JOBS`** (in `pipeline.py`) is an in-memory job store used as the
  no-Celery fallback — it is not shared across processes, which is acceptable
  for a dev fallback but should be called out as a known limitation.

> **How to frame it if asked:** "The repo is a monorepo — `backend/` (Python)
> and `frontend/` (Next.js) as siblings. The backend is layered and follows
> standard patterns — repository, dependency injection, typed schemas,
> environment config. A small thing I'd still polish is fixing the
> `scrapping_module` spelling."

---

## 10. Presentation cheat-sheet — likely tutor questions

Each folder README has detailed Q&A; these are the **whole-backend** ones.

**Q: Walk me through what happens when a user starts an analysis.**
A: The frontend calls `POST /api/v1/pipeline/run`. The API creates a job and
launches `SalesPipeline.run()` in the background. The pipeline runs 9 agents in
order, persisting results to PostgreSQL after each stage and streaming live
progress over SSE. The frontend polls `/pipeline/status/{id}` and listens to
`/pipeline/stream/{id}`.

**Q: What is an "agent" here?**
A: A small, stateless class with one responsibility — e.g. `CompetitorAgent`
discovers competitors. It builds a prompt, calls the LLM (or a scraper), parses
the result into a Pydantic schema, and returns it. Agents don't know about each
other; the pipeline wires them together.

**Q: What is RAG and why use it?**
A: Retrieval-Augmented Generation. Scraped text is embedded and stored in a
vector DB; relevant chunks are retrieved by similarity and fed into the LLM
prompt. It grounds answers in real evidence and prevents hallucination.

**Q: Why FastAPI and async?**
A: The workload is I/O-bound — LLM calls, scraping, DB queries all involve
waiting. `async`/`await` lets the server handle many of those concurrently
without threads, and lets the pipeline scrape many sites in parallel.

**Q: How do you handle a website that won't load or a stage that fails?**
A: The scraper retries with backoff and falls back from httpx to a headless
browser; if it still fails, that competitor is just marked unscraped. At the
pipeline level, `_run_stage()` catches the error, records it, and continues.

**Q: How does the frontend show live agent logs?**
A: Server-Sent Events. The pipeline pushes events into a per-job queue
(`StreamManager`); the `/pipeline/stream/{id}` endpoint drains that queue and
streams the events to the browser.

**Q: Where would this break at scale, and how would you fix it?**
A: The in-memory job store and SSE queues are per-process. For scale I'd run the
pipeline on Celery workers (already supported) and move job state to Redis/DB so
any process can serve status and streams.

---

## 11. Where to read next

| To understand… | Read |
|---|---|
| The agents | `app/agents/README.md` |
| The orchestrator | `app/pipelines/README.md` |
| LLM / RAG / scraping services | `app/services/README.md` |
| The REST endpoints | `app/api/README.md` |
| Database & vector store | `app/db/README.md` |
| Data contracts | `app/schemas/README.md` |
| Logging / auth / streaming | `app/core/README.md` |
| Config & env vars | `app/config/README.md` |
| Background jobs | `app/workers/README.md` |
| Social scraping internals | `scrapping_module/README.md` |
| The test suite | `tests/README.md` |

Every backend `.py` file also has module, class, and inline comments written
specifically so you can read the code and explain it.
