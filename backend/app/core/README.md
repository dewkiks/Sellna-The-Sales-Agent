# app/core — Cross-cutting Infrastructure

This package contains the foundational infrastructure that every other layer of the Sellna.ai backend depends on. It has no business logic of its own; instead it provides the plumbing that wires the application together: FastAPI dependency injection, structured logging, JWT-based security, and the asyncio-queue mechanism that powers live pipeline progress streaming to the browser.

## Files

| File | Description |
|---|---|
| `__init__.py` | Package docstring; no executable code |
| `dependencies.py` | FastAPI `Depends()` factories for the Settings singleton and managed async DB sessions |
| `logging.py` | Configures structlog + Python stdlib logging; exposes `get_logger()` and `configure_logging()` |
| `security.py` | JWT token creation, verification, and `require_role()` dependency factory for RBAC |
| `stream_manager.py` | Per-job `asyncio.Queue` registry powering the Server-Sent Events live feed |

## How this folder fits the architecture

```
Browser (EventSource)
        ↑ SSE
  FastAPI route (GET /stream/{job_id})
        ↑ async generator
  stream_manager.subscribe(job_id)
        ↑ asyncio.Queue events
  Agent callback (make_stream_cb)
        ↑ publishes tokens
  LLM streaming response
```

Every API route uses `DbSession` and/or `SettingsDep` from `dependencies.py`. All log output from agents, services, and routes passes through `logging.py`. Protected routes call `require_role()` from `security.py`. Live pipeline progress travels through `stream_manager.py`.

## Likely exam questions

**Q: How does live pipeline progress reach the browser?**
A: Each pipeline job gets a dedicated `asyncio.Queue` in `StreamManager`. Agents push token/progress events into the queue via a callback built by `make_stream_cb()`. The SSE endpoint's async generator pulls events off the queue and formats them as `data:` lines over the persistent HTTP connection. A `{"type": "done"}` event closes the generator.

**Q: What is the purpose of `configure_logging()` and when is it called?**
A: `configure_logging()` wires structlog to Python's stdlib logging so that every log record — whether from structlog or from third-party libraries like uvicorn and httpx — passes through the same processor chain (adding service name, environment, and a UTC timestamp) and is rendered in JSON or coloured-console format based on the `LOG_FORMAT` setting. It is called once at app startup in `main.py`.

**Q: How does the JWT authentication flow work?**
A: A login/bootstrap endpoint calls `create_access_token(sub, role)` which signs a JWT with HS256 using `SECRET_KEY`. On subsequent requests the client sends the token in an `Authorization: Bearer` header. FastAPI's `HTTPBearer` dependency extracts it; `_get_current_token` decodes and validates the signature and expiry; `require_role()` additionally checks the embedded role claim against the required roles for that route.

**Q: Why does `get_db` use a generator with `yield`?**
A: Using `yield` makes `get_db` a FastAPI generator dependency. Code before `yield` (open session) runs before the route handler; code after `yield` (commit or rollback, then close) runs as cleanup after the response is sent. This guarantees the session is always closed even if an exception occurs.

**Q: What happens if the SSE client disconnects while the pipeline is running?**
A: The `asyncio.Queue` for the job continues to receive events from the agents (which are unaware of the client). Events accumulate up to `maxsize=4000`; beyond that, `put_nowait()` silently drops events. Once the SSE generator's HTTP response is closed, `cleanup(job_id)` is called to delete the queue. The pipeline itself runs to completion regardless.

**Q: What does `cache_logger_on_first_use=True` do in structlog?**
A: It freezes the processor chain into a compiled form the first time `get_logger()` is called for a given logger name. Subsequent calls skip the chain-construction step entirely, giving a performance improvement in hot paths such as LLM token streaming.
