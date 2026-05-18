"""Celery application instance.

Celery is a distributed task queue.  FastAPI enqueues tasks (via the Celery
broker, here Redis db=1) and separate worker processes pick them up, execute
them, and store results in the result backend (Redis db=2).

Key configuration choices explained
------------------------------------
task_acks_late=True
    The worker acknowledges a task only AFTER it finishes, not when it picks
    it up.  If the worker crashes mid-task, the broker re-queues it for
    another worker to retry — crucial for a long-running pipeline.

worker_prefetch_multiplier=1
    Each worker process fetches at most 1 pending task at a time.  Without
    this, a worker might hoard tasks (prefetch many) while others sit idle.
    The pipeline is memory/CPU-intensive so even distribution matters.

task_track_started=True
    The task records a "STARTED" state in Redis as soon as execution begins,
    allowing the API's /status endpoint to distinguish "waiting" from "running".

result_expires=86_400 (24 hours)
    Completed task results are kept in Redis for one day then auto-deleted,
    preventing unbounded Redis memory growth.

Worker startup:
    celery -A app.workers.celery_app worker --loglevel=info --concurrency=2

Beat scheduler (optional, for periodic tasks):
    celery -A app.workers.celery_app beat --loglevel=info
"""

from __future__ import annotations

from celery import Celery

from app.config import get_settings

_s = get_settings()

# ``include`` tells Celery which modules contain @celery_app.task decorators.
# These are auto-discovered when a worker process starts.
celery_app = Celery(
    "sales_ai",
    broker=_s.celery_broker_url,       # Redis db=1 — task queue
    backend=_s.celery_result_backend,  # Redis db=2 — stores task results/state
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task behaviour
    task_track_started=True,
    task_acks_late=True,            # re-queue on worker crash
    worker_prefetch_multiplier=1,   # one task at a time per worker slot (pipeline is heavy)
    # Result expiry — keep results for 24 h then auto-delete from Redis
    result_expires=86_400,
    # Retries
    task_max_retries=2,
    task_default_retry_delay=30,
)
