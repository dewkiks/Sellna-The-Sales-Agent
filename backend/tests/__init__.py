# sales_agentic_ai/tests/__init__.py
"""
tests/ — Pytest test suite for the Sellna.ai backend.

The test suite is designed to run without any external services:
  - PostgreSQL is replaced by an in-memory SQLite database (via aiosqlite).
  - LLM API calls are replaced by unittest.mock.AsyncMock objects.
  - HTTP clients are replaced by httpx.AsyncClient with ASGITransport,
    which sends requests directly to the FastAPI ASGI app in-process.

All shared infrastructure (DB engine, sessions, test client) is provided as
pytest fixtures defined in conftest.py.
"""
