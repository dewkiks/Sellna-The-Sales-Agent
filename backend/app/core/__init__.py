# sales_agentic_ai/app/core/__init__.py
"""
app/core — Cross-cutting concerns for the Sellna.ai backend.

This package centralises the infrastructure-level building blocks that every
other layer of the application depends on:

- dependencies.py  : FastAPI Depends() factories for settings and DB sessions
- logging.py       : structlog configuration (structured JSON or console output)
- security.py      : JWT creation and role-based access-control dependencies
- stream_manager.py: Per-job asyncio queues powering the SSE live-progress feed

Nothing in this package contains business logic — it is purely plumbing.
"""
