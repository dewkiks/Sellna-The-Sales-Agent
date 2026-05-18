# tests/ — Pytest Test Suite

This directory contains the automated test suite for the Sellna.ai backend. All tests are designed to run without any external services: there is no real PostgreSQL database, no live LLM API keys, and no running HTTP server. Instead, a set of shared fixtures (defined in `conftest.py`) provide in-process replacements for each dependency.

## Files

| File | Description |
|---|---|
| `__init__.py` | Package marker with a summary of the no-external-services test strategy |
| `conftest.py` | Shared pytest fixtures: in-memory SQLite engine, per-test DB session, ASGI HTTP client |
| `test_api_company.py` | Integration tests for the Company Intelligence REST endpoints (mocked DomainAgent) |
| `test_domain_agent.py` | Unit tests for DomainAgent — verifies JSON parsing with a mocked LLMService |
| `test_scraping_service.py` | Unit tests for ScrapingService — verifies result mapping with a mocked Scraper |
| `test_utils.py` | Pure-function unit tests for `app/utils/text_cleaning` utility functions |

## How this folder fits the architecture

```
Test runner (pytest)
    ↓ loads
conftest.py
    ↓ provides fixtures
  test_engine    → in-memory SQLite (replaces PostgreSQL)
  db_session     → per-test session with automatic rollback
  client         → httpx ASGI client (replaces real HTTP server + TCP)
    ↓ used by
test_api_company.py  ← uses client + mocks DomainAgent.run
test_domain_agent.py ← uses no fixtures; mocks LLMService.chat
test_scraping_service.py ← uses no fixtures; mocks Scraper class
test_utils.py        ← uses no fixtures; pure Python assertions
```

## Running the tests

```bash
# From the project root (with uv):
uv run pytest tests/ -v

# Run a single file:
uv run pytest tests/test_domain_agent.py -v

# Run with coverage:
uv run pytest tests/ --cov=app --cov-report=term-missing
```

## Likely exam questions

**Q: How do tests run without a real PostgreSQL database or API key?**
A: `conftest.py` creates an in-memory SQLite database (`sqlite+aiosqlite:///:memory:`) and uses FastAPI's `dependency_overrides` to replace the production `get_db` dependency with one that returns the test session. LLM calls are intercepted by `unittest.mock.AsyncMock` patching `LLMService.chat`, so no API key or internet connection is needed.

**Q: Why does `db_session` roll back after each test instead of committing?**
A: Rolling back ensures that data written by one test is never visible to the next, keeping tests fully isolated even though they share the same in-memory engine. If tests committed, data from test A could affect assertions in test B.

**Q: What is `ASGITransport` and why is it used instead of a real HTTP client?**
A: `httpx.ASGITransport` calls the FastAPI application's ASGI interface directly in-process, bypassing TCP sockets and port binding entirely. This makes tests faster, deterministic, and runnable in any environment (including CI without network access).

**Q: Why is the `event_loop` fixture scoped to "session" instead of the default "function"?**
A: The `test_engine` fixture is also session-scoped (schema creation should happen once). pytest-asyncio requires that async fixtures share an event loop with their dependents. By overriding `event_loop` to session scope, all async fixtures and tests share the same loop throughout the entire test run.

**Q: What does `patch("app.agents.domain_agent.DomainAgent.run", new_callable=AsyncMock)` actually replace?**
A: It replaces the `run` method on the `DomainAgent` class in the module where it is defined. Any code that calls `DomainAgent().run(...)` during the `with patch(...)` block will call the mock instead, returning the pre-configured `mock_run.return_value` without touching the LLM or any network.

**Q: Why are the utility tests in `test_utils.py` not async and use no fixtures?**
A: The functions under test (`clean_text`, `truncate`, etc.) are pure synchronous functions with no I/O, no DB, and no external dependencies. Pure synchronous pytest tests are simpler, faster, and do not need an event loop.
