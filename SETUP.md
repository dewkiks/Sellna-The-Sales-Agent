# Sellna.ai — Setup & Run Guide

Everything you need to install, configure, and run Sellna.ai locally.

The repo is a monorepo:

```
sellna.ai/
├── backend/    ← Python API + 9-agent pipeline + scrapers   (run on :8001)
└── frontend/   ← Next.js web app                            (run on :8080)
```

---

## 1. Prerequisites

Install these once:

| Tool | Why | Notes |
|---|---|---|
| **Python 3.11+** | Backend | `python --version` |
| **Node.js 18+** | Frontend | `node --version` |
| **uv** *or* **pip** | Backend deps | uv recommended — [install](https://docs.astral.sh/uv/) |
| **Docker Desktop** | Postgres / Redis / Qdrant | Easiest way to get the databases |
| **An LLM API key** | The agents call an LLM | Free option: [Groq](https://console.groq.com/keys) |

> Windows users: commands below are PowerShell. macOS/Linux equivalents are noted where they differ.

---

## 2. Infrastructure (databases) — Docker

The backend needs **PostgreSQL** (required) and **Qdrant** (for RAG). Redis is optional.
The quickest way is Docker Compose:

```powershell
cd backend\docker
docker compose up -d postgres redis qdrant
```

This starts:

| Service | Port | Required? |
|---|---|---|
| PostgreSQL | 5432 | **Yes** — the app creates its tables on startup |
| Qdrant (vector DB) | 6333 | Recommended — needed for the RAG stages |
| Redis | 6379 | Optional — only for Celery; the pipeline has an in-process fallback |

Leave these running in the background. To stop them later: `docker compose down`.

> Don't want Docker? Install PostgreSQL and Qdrant natively and point `.env` at them.

---

## 3. Backend — install

```powershell
cd backend
```

### Option A — uv (recommended)

```powershell
uv sync                       # creates backend/.venv and installs everything
uv run playwright install chromium
```

### Option B — plain venv + pip

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1     # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

`playwright install chromium` downloads the headless browser used to scrape
JavaScript-heavy pages — it is a one-time step.

---

## 4. Backend — configure (`.env`)

The backend reads configuration from `backend/.env`. Create it from the template:

```powershell
Copy-Item .env.example .env    # macOS/Linux: cp .env.example .env
```

Then open `backend/.env` and set, at minimum:

| Variable | What to put |
|---|---|
| `SECRET_KEY` | Any 64-char hex — generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `LLM_PROVIDER` | `groq` (default), or `openai` / `openrouter` / `gemini` / `nvidia` / `ollama` |
| `GROQ_API_KEY` | Your key — only fill in the key for the provider you chose |
| `DATABASE_URL` | Leave the default if you used Docker: `postgresql+asyncpg://postgres:postgres@localhost:5432/sales_ai` |
| `QDRANT_URL` | Leave default `http://localhost:6333` if you used Docker |

Everything else has sensible defaults (embeddings run locally on CPU, so no
embedding API key is needed).

> **Fully free, no API key:** set `LLM_PROVIDER=ollama`, run `docker compose up -d ollama`,
> then `docker exec sales_ai_ollama ollama pull llama3`.

---

## 5. Frontend — install & configure

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local    # macOS/Linux: cp .env.example .env.local
```

Then edit `frontend/.env.local`:

| Variable | What to put |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Your Supabase project URL — **required for sign-in / sign-up** |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Your Supabase publishable (anon) key |
| `NEXT_PUBLIC_API_BASE_URL` | Backend URL — optional, defaults to `http://localhost:8001/api/v1` |

Get the two Supabase values from the [Supabase dashboard](https://supabase.com/dashboard)
→ your project → **Project Settings → API**. Without them the app shows
**"Auth is not configured"** and the login / signup screens are disabled
(the rest of the app still renders).

---

## 6. Running everything

Open a terminal per service.

### Backend API (required)

```powershell
cd backend
uv run python main.py
#   → http://localhost:8001        API
#   → http://localhost:8001/docs   interactive Swagger docs
```

*(pip users: activate the venv first, then `python main.py`.)*

### Frontend (required)

```powershell
cd frontend
npm run dev
#   → http://localhost:8080
```

### Celery worker (optional)

Only needed if you want pipeline runs processed by Celery instead of the
built-in in-process fallback. Requires Redis to be running.

```powershell
cd backend
uv run celery -A app.workers.celery_app worker --loglevel=info
```

### Standalone scraper API (optional)

A separate, lightweight app exposing just the web/social scrapers:

```powershell
cd backend
uv run uvicorn scraper_standalone:app --port 8000
#   → http://localhost:8000
```

### Or: run the whole backend stack in Docker

Instead of running the API locally, you can run everything (API, worker,
databases) in containers:

```powershell
cd backend\docker
docker compose up -d
```

You still run the **frontend** locally with `npm run dev`.

---

## 7. Tests

No real database or API key needed — the suite uses in-memory SQLite and a
mocked LLM:

```powershell
cd backend
uv run --extra dev pytest tests/ -v
#   pip users:  pip install pytest pytest-asyncio anyio  →  pytest tests/ -v
```

---

## 8. Ports reference

| Port | Service |
|---|---|
| 8001 | Backend API (`main.py`) |
| 8080 | Frontend (Next.js) |
| 8000 | Standalone scraper API (optional) |
| 5432 | PostgreSQL |
| 6333 | Qdrant |
| 6379 | Redis |
| 11434 | Ollama (optional local LLM) |
| 5555 | Flower — Celery monitoring (optional) |

---

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| App won't start, DB connection error | Postgres isn't running — `docker compose up -d postgres`, or check `DATABASE_URL` |
| `playwright` / browser errors when scraping | Run `playwright install chromium` |
| RAG / gap-analysis stages fail | Qdrant isn't running — `docker compose up -d qdrant` |
| LLM errors / 401 | Wrong or missing key for the `LLM_PROVIDER` set in `.env` |
| Pipeline runs but no Celery | Expected — it falls back to in-process `BackgroundTasks`. Start a worker only if you want Celery |
| Frontend can't reach the API | Make sure the backend is up on :8001, and `NEXT_PUBLIC_API_BASE_URL` matches |

For backend architecture and a presentation cheat-sheet, see
[`backend/BACKEND.md`](backend/BACKEND.md).
