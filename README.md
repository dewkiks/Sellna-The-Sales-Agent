# Sellna.ai

> Multi-agent B2B sales-intelligence platform. Enter a company domain; a
> pipeline of 9 AI agents returns competitor analysis, market gaps, Ideal
> Customer Profiles, buyer personas, and personalized outreach copy.

This repository is a **monorepo** with two independent halves:

```
sellna.ai/
├── backend/    ← Python API — FastAPI, the 9-agent pipeline, web + social scrapers
└── frontend/   ← Next.js web app
```

> **First time here? → [SETUP.md](SETUP.md)** — the complete install, configuration
> (Docker, venv, `.env`) and run guide. The blocks below are the short version.

---

## Backend

FastAPI · SQLAlchemy 2 (async) · PostgreSQL · Qdrant (RAG) · Playwright scraping.
All Python lives in `backend/` — run every backend command from there.

```powershell
cd backend
uv sync
playwright install chromium
Copy-Item .env.example .env          # add your LLM key + DATABASE_URL
uv run python main.py                # API → http://localhost:8001/docs
```

Full guide: **[backend/BACKEND.md](backend/BACKEND.md)** — architecture, the
9-stage pipeline, scraping subsystems, and a presentation cheat-sheet. Every
backend sub-folder also carries its own `README.md`.

## Frontend

Next.js app (see `frontend/`).

```powershell
cd frontend
npm install
npm run dev                          # → http://localhost:8080
```

The frontend calls the backend at `http://localhost:8001/api/v1` — override with
the `NEXT_PUBLIC_API_BASE_URL` environment variable.

---

## Tech stack

| Layer | Stack |
|---|---|
| Backend | FastAPI · SQLAlchemy 2 async · PostgreSQL · Qdrant · Celery (optional) |
| AI | OpenAI-compatible LLM · RAG · a 9-agent sales-intelligence pipeline |
| Scraping | httpx + Playwright (`backend/webscraper/`) · social scraper (`backend/scrapping_module/`) |
| Frontend | Next.js · React · TypeScript |
| Infra | Docker Compose — `backend/docker/docker-compose.yml` (Postgres, Redis, Qdrant, Ollama) |

## Layout

| Path | What |
|---|---|
| `backend/app/` | The FastAPI application — API, agents, pipeline, services, db |
| `backend/webscraper/` | Generic web-scraping engine (httpx + Playwright) |
| `backend/scrapping_module/` | Social-media scraper (LinkedIn, Instagram) |
| `backend/scripts/` | Manual dev/debug scripts |
| `backend/tests/` | pytest suite (in-memory SQLite, mocked LLM) |
| `backend/docker/` | Dockerfile + Compose stack |
| `frontend/` | Next.js web app |
