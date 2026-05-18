"""Shared FastAPI dependencies — injected into routes via Depends().

This module defines two dependency types that FastAPI resolves automatically
when they appear in route function signatures:

1. SettingsDep  — provides the cached application Settings object.
2. DbSession    — opens an async SQLAlchemy session, yields it to the route,
                  commits on success, rolls back on any exception, and always
                  closes the session when the response is sent.

Route handlers declare these via Python type annotations, e.g.:

    async def my_route(db: DbSession, cfg: SettingsDep): ...
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.postgres import async_session_factory


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def get_app_settings() -> Settings:
    """Thin wrapper so FastAPI's dependency injection can call get_settings().

    get_settings() is itself cached via @lru_cache, so this never constructs
    more than one Settings instance per process lifetime.
    """
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session, commit on success, rollback on error.

    FastAPI calls this as a generator dependency: code before ``yield`` runs
    before the route handler; code after ``yield`` runs as cleanup once the
    response has been sent (similar to a try/finally context manager).
    """
    async with async_session_factory() as session:
        try:
            yield session          # hand the open session to the route handler
            await session.commit() # auto-commit if the handler raised no exception
        except Exception:
            await session.rollback()  # undo any partial writes on error
            raise


# Annotated type alias — routes declare ``db: DbSession`` to receive the
# managed session without writing Depends(get_db) on every endpoint.
DbSession = Annotated[AsyncSession, Depends(get_db)]
