# app/api — HTTP API Layer

## Purpose

The `app/api/` package is the HTTP surface of Sellna.ai.  It contains one
central router (`router.py`) and a versioned sub-package (`v1/`) with one
FastAPI `APIRouter` per domain area.  `router.py` imports every v1 sub-router
and merges them into a single `api_router` object, which `main.py` registers
on the FastAPI application under the `/api/v1` prefix.  Every URL the React
frontend calls is handled by a handler function defined in one of these files.

---

## File Map

| File | Description | Endpoints / Paths |
|---|---|---|
| `router.py` | Central assembly point — imports and mounts all v1 sub-routers onto `api_router`. | *(no routes of its own)* |
| `v1/company.py` | List and delete stored companies (records are created by the pipeline). | `GET /company/`, `DELETE /company/{id}` |
| `v1/competitors.py` | Competitor discovery, storage, and website scraping/cleaning. | `POST /competitors/discover/{id}`, `GET /competitors/{id}`, `POST /competitors/scrape/{id}` |
| `v1/icp.py` | Market-gap analysis (GapAnalysisAgent) then ICP generation (ICPAgent). | `POST /icp/generate`, `GET /icp/{id}` |
| `v1/personas.py` | Buyer persona generation from stored ICPs (PersonaAgent). | `POST /personas/generate`, `GET /personas/{id}` |
| `v1/outreach.py` | Outreach copy generation, manual editing, and retrieval. | `POST /outreach/generate`, `PATCH /outreach/asset/{id}`, `GET /outreach/{id}` |
| `v1/analytics.py` | Performance aggregation by channel and 6-week time-series. | `GET /analytics/performance/{id}` |
| `v1/pipeline.py` | Full 9-agent pipeline: async-queued (Celery or BackgroundTasks fallback), job status polling, SSE stream, result retrieval, and abort. | `POST /pipeline/run`, `GET /pipeline/status/{id}`, `GET /pipeline/stream/{id}`, `GET /pipeline/result/{id}`, `POST /pipeline/abort/{id}` |
| `v1/dashboard.py` | Read-only aggregate counts and cross-table activity feed for the frontend dashboard. | `GET /dashboard/summary`, `GET /dashboard/activity` |
| `v1/scrapers.py` | On-demand web scraping (with optional JS rendering) and social profile scraping. Also surfaces pipeline-collected social intelligence. | `POST /scrapers/web`, `POST /scrapers/social`, `GET /scrapers/social/{id}` |
| `v1/chat.py` | Streaming companion-chat assistant grounded in app FAQs + live pipeline data. | `POST /chat` |
| `v1/ui.py` | Server-driven UI configuration — landing page copy, form options, auth copy, persona section definitions. No DB or agent calls. | `GET /ui/landing`, `GET /ui/company-input`, `GET /ui/auth-copy`, `GET /ui/personas` |

---

## Architecture Fit

```
React Frontend
     |
     |  HTTP (REST + SSE)
     v
FastAPI app  (main.py)
     |
     +-- /api/v1/*  <-- app/api/router.py + app/api/v1/*.py   ← YOU ARE HERE
               |
               |  dependency injection (DbSession via app/core/dependencies.py)
               |  structured logging  (structlog via app/core/logging.py)
               v
     Agents (app/agents/)          Services (app/services/)
         |                               |
         v                               v
     LLM (OpenAI-compat)           Postgres (SQLAlchemy async)
     Qdrant vector DB              Qdrant (via app/db/vector_store.py)
     httpx / Playwright scraping
```

The API layer is intentionally thin: handlers load prerequisites from the DB,
instantiate the relevant agent or repository, delegate the actual work, persist
results, and return a JSON response.  No business logic lives in the handlers.

The pipeline route (`pipeline.py`) is the exception — it contains non-trivial
orchestration logic for the Celery/BackgroundTasks fallback, the SSE streaming
bridge, and the in-memory `_LOCAL_JOBS` state store.

---

## Likely Exam Questions

**Q1. How does `POST /pipeline/run` work?**

The handler generates a `job_id` UUID and then decides how to run the pipeline:

1. It pings live Celery workers via `inspect().ping(timeout=1)`.  If at least
   one worker responds, the job is dispatched via `run_pipeline_task.apply_async()`
   and the Celery task id becomes the `job_id`.
2. If no workers are available (or Celery is not installed), it falls back to
   FastAPI's `BackgroundTasks`.  Before adding the background coroutine, it
   pre-registers the job in `_LOCAL_JOBS` and calls `stream_manager.create(job_id)`
   so the SSE queue exists before the frontend connects.

In both cases HTTP 202 Accepted is returned immediately with `job_id` and a
`poll_url`.

---

**Q2. What is `GET /pipeline/stream/{job_id}` for?**

It is a Server-Sent Events (SSE) endpoint.  It opens a persistent HTTP
connection and pushes events as the pipeline executes.  Each event is a JSON
object like `{"type": "token", "agent": "ICP Agent", "content": "..."}`.  The
React frontend subscribes immediately after receiving the `job_id` and uses the
stream to animate the "agent thinking" UI in real time.  The connection ends
when the pipeline publishes a `{"type": "done"}` event.

---

**Q3. Why is there a Celery fallback, and what is `_LOCAL_JOBS`?**

`apply_async()` always succeeds even when no Celery worker is running — tasks
just queue forever.  To avoid silent hang-forever behaviour, the handler first
pings for live workers.  When none are found it falls back to FastAPI's
`BackgroundTasks`, which runs the pipeline in the same process after the
response is sent.

`_LOCAL_JOBS` is a module-level Python dictionary that stores the state
(`state`, `progress`, `status_msg`, `result`, `error`, `company_id`) for
every background-task job.  It is consulted by `GET /pipeline/status` and
`GET /pipeline/result` before they attempt to query Celery.  It is not
persistent — data is lost on server restart — making it suitable only for
development.

---

**Q4. How does the frontend track a running job?**

Two mechanisms work in parallel:

- **Polling**: `GET /pipeline/status/{job_id}` returns `state` (RUNNING /
  SUCCESS / FAILURE) and a `progress` percentage (0–100).  The frontend polls
  this on an interval to update the progress bar.
- **SSE streaming**: `GET /pipeline/stream/{job_id}` delivers token-by-token
  LLM output and agent lifecycle events so the UI can show what the AI is
  "thinking" at each step without waiting for the full pipeline to finish.

When status returns `SUCCESS`, the frontend calls `GET /pipeline/result/{job_id}`
to retrieve the complete structured output.

---

**Q5. What must happen before `POST /icp/generate` can be called?**

A company record with its `CompanyAnalysis` must already exist in Postgres —
that record is created by `POST /pipeline/run` (the DomainAgent stage).  The
endpoint also loads competitor `clean_data` as RAG context for the
GapAnalysisAgent; this data is only available if competitor discovery and
`POST /competitors/scrape` have also been run.  Without it, gap analysis still
works but with less grounded context.

---

**Q6. What is the role of `router.py` and how does it relate to `main.py`?**

`router.py` creates a single `api_router = APIRouter()` and calls
`include_router()` for each of the eleven v1 sub-routers.  In `main.py`, the
FastAPI app registers `api_router` with `app.include_router(api_router, prefix="/api/v1")`.
This two-level structure keeps each domain area self-contained (its own
module, prefix, and tag) while presenting a single unified router to the
application.

---

**Q7. What does `v1/ui.py` do and why does it exist?**

`ui.py` returns static JSON configuration for the React frontend — sidebar
navigation items, landing page copy, form dropdown options, and marketing
bullets.  It makes no DB queries and calls no agents.  The design principle
is that the frontend contains zero hardcoded display strings; all content
comes from the API.  This lets content and configuration changes be deployed
server-side without a frontend rebuild or redeployment.
