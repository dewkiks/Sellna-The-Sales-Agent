# app/workers/__init__.py
"""
app/workers — Celery background-worker package.

Contains the Celery application instance (celery_app.py) and the task
definitions (tasks.py) that run the sales pipeline and outreach generation
in separate worker processes.

To start a Celery worker from the project root:
    celery -A app.workers.celery_app worker --loglevel=info --concurrency=2

The FastAPI application itself does NOT need to import from this package at
runtime; it enqueues tasks via the Celery broker (Redis) and polls results
through the same broker.
"""
