# app/workers — Celery Background Workers

This package contains the Celery application instance and task definitions that run heavy, long-lived operations (the full 9-agent sales pipeline and per-persona outreach generation) outside the FastAPI request/response cycle. When a user submits a company domain, FastAPI enqueues a Celery task, returns a job ID immediately, and the actual pipeline work happens in a separate worker process.

## Files

| File | Description |
|---|---|
| `__init__.py` | Package marker with usage notes |
| `celery_app.py` | Celery application instance, broker/backend URLs, and task configuration |
| `tasks.py` | `run_pipeline_task` and `run_outreach_task` — the two Celery tasks |

## How this folder fits the architecture

```
User → POST /api/v1/pipeline/run
         ↓
   FastAPI enqueues task → Redis (broker, db=1)
         ↓
   Celery worker picks up task
         ↓
   asyncio.run(pipeline._run())   ← bridge from sync Celery to async pipeline
         ↓
   SalesPipeline.run() (all 9 agents)
         ↓
   Result stored in Redis (backend, db=2)
         ↓
User → GET /api/v1/pipeline/status/{job_id} → reads AsyncResult from Redis
```

Redis is used for three separate purposes, each on a different database number: `db=0` for general caching, `db=1` as the Celery task broker (job queue), and `db=2` as the Celery result backend (completed task data and progress state).

## Starting workers

```bash
# Start a worker (from project root, with uv):
celery -A app.workers.celery_app worker --loglevel=info --concurrency=2

# Optional beat scheduler for periodic tasks:
celery -A app.workers.celery_app beat --loglevel=info
```

## Likely exam questions

**Q: Why does the pipeline run inside `asyncio.run()` in a Celery task?**
A: Celery workers are synchronous — they do not run an asyncio event loop. The Sales AI pipeline is fully async (async SQLAlchemy, async HTTP, async LLM calls). `asyncio.run(_run())` creates a new event loop, runs the entire async pipeline to completion inside the synchronous Celery worker thread, then tears the loop down. It is the standard bridge between a sync caller and an async codebase.

**Q: What does `task_acks_late=True` mean and why is it used here?**
A: By default Celery acknowledges (removes) a task from the broker queue as soon as a worker picks it up. With `task_acks_late=True`, acknowledgement happens only after the task finishes successfully. If the worker crashes mid-pipeline, the broker re-queues the task for another worker to retry, preventing silent data loss on long-running jobs.

**Q: Why does `_get_session()` create a fresh engine per task instead of reusing a global pool?**
A: SQLAlchemy connection pools are not safe to share across forked processes. Each Celery worker is a separate process (possibly on a different machine). Creating a fresh engine per task is the safe pattern; `pool_pre_ping=True` discards any stale TCP connections from before the fork.

**Q: How does the pipeline report progress back to the API while running inside Celery?**
A: The `on_prog` callback inside `run_pipeline_task` calls `self.update_state(state="RUNNING", meta={...})`. This writes progress metadata into Redis via the Celery result backend. The FastAPI status endpoint reads `AsyncResult(job_id).info` from Redis and returns the latest progress to the frontend.

**Q: What happens if a pipeline task fails?**
A: The exception is caught, logged with a full traceback, and `self.retry(exc=exc, countdown=30)` is called. Celery re-queues the task with a 30-second delay. `max_retries=1` means the pipeline is attempted at most twice total. After all retries are exhausted Celery marks the task as FAILURE in Redis.

**Q: Why are imports like `from app.pipelines.sales_pipeline import SalesPipeline` placed inside the task function rather than at the module top?**
A: Lazy imports keep worker startup fast (the pipeline module and its dependencies are heavy) and also avoid circular imports that can arise when Celery loads the task module before the full application is initialised.
