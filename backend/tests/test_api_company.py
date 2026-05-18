"""API integration tests for the Company Intelligence REST endpoints.

These tests exercise the full HTTP request/response cycle through FastAPI,
using the ``client`` fixture from conftest.py (in-memory SQLite + ASGI transport).

Test coverage:
  - test_health_check    : /health returns 200 {"status": "ok"}
  - test_list_companies  : GET /api/v1/company/ returns a paginated list
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    """Verify the /health endpoint returns HTTP 200 with {"status": "ok"}.

    This is the simplest smoke test — it confirms the app starts, routes are
    registered, and the ASGI transport works correctly.
    """
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_list_companies(client):
    """GET /api/v1/company/ should return a paginated list response.

    Verifies the response schema contains "companies" (list) and "total"
    (count), regardless of how many records are in the test DB.
    """
    response = await client.get("/api/v1/company/")
    assert response.status_code == 200
    data = response.json()
    assert "companies" in data
    assert "total" in data
