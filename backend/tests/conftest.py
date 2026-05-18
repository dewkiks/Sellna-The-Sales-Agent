"""Pytest configuration and shared fixtures.

This module is automatically loaded by pytest before any test file runs.
It provides three layers of test infrastructure:

1. event_loop (session-scoped)
   A single asyncio event loop shared across all async tests in the session.
   Without this, each test would get a fresh loop, causing session-scoped
   async fixtures to fail.

2. test_engine / db_session (DB layer)
   ``test_engine`` creates an in-memory SQLite database and runs
   ``Base.metadata.create_all`` to build the schema — no PostgreSQL needed.
   ``db_session`` opens a session for each test and rolls back after it
   finishes, so tests never pollute each other's data.

3. client (HTTP layer)
   An httpx AsyncClient backed by ASGITransport sends requests directly to
   the FastAPI ASGI app in-process (no TCP sockets, no running server).
   It replaces the real ``get_db`` dependency with one that yields the test
   DB session, ensuring HTTP tests use the same isolated SQLite database.
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.postgres import Base


# ---------------------------------------------------------------------------
# Use in-memory SQLite for tests (no real DB needed)
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Provide a single asyncio event loop for the entire test session.

    pytest-asyncio creates a new loop per test by default (function scope).
    Overriding to session scope is required here because ``test_engine`` is
    also session-scoped — async fixtures that use the engine must share a loop.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create an in-memory SQLite engine and apply the full DB schema.

    ``sqlite+aiosqlite:///:memory:`` keeps the database entirely in RAM —
    no files, no cleanup, instant setup.  ``Base.metadata.create_all`` mirrors
    what Alembic migrations do in production, creating all tables defined in
    the SQLAlchemy models.

    Session-scoped so schema creation happens once for the whole test run.
    """
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        # run_sync() executes the synchronous SQLAlchemy DDL inside the async context.
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()  # close all connections when the session ends


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Open an async DB session and roll back all changes after each test.

    Rolling back (rather than committing) after each test ensures that data
    written by one test never leaks into the next — tests are fully isolated
    even though they share the same in-memory database engine.
    """
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()  # undo any writes made during the test


@pytest_asyncio.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client wired to the FastAPI app with the test DB session.

    ASGITransport sends requests directly to the ASGI app (no TCP sockets
    or running server needed).  The ``dependency_overrides`` dict replaces
    the production ``get_db`` dependency with one that returns the test
    SQLite session, so HTTP route handlers read/write the in-memory DB.
    """
    from app.main import app
    from app.core.dependencies import get_db

    # Provide the already-open test session instead of opening a new DB connection.
    async def override_get_db():
        yield db_session

    # FastAPI respects dependency_overrides at request time — no restart needed.
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c

    # Remove overrides after the test so other fixtures see the real dependencies.
    app.dependency_overrides.clear()
