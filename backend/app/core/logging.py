"""Structured logging via structlog.

Structlog is a library that pre-processes log records through a chain of
"processor" functions before handing them off to the standard Python logging
system.  This module:

1. Defines two custom processors (_add_service_info, _add_timestamp) that
   stamp every log record with the app name, environment, and a UTC timestamp.
2. configure_logging() wires structlog to Python's stdlib logging so that
   third-party libraries (uvicorn, httpx, sqlalchemy) also pass through the
   same processor chain and end up with the same format.
3. Output format is controlled by LOG_FORMAT in .env:
   - "json"    → machine-readable, one JSON object per line (production)
   - "console" → coloured human-readable output (development default)

Usage anywhere in the app:
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("event", module="my_module", key="value")
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from app.config import get_settings

_settings = get_settings()


# ---------------------------------------------------------------------------
# Custom processors
# ---------------------------------------------------------------------------


def _add_service_info(
    logger: WrappedLogger, method: str, event_dict: EventDict
) -> EventDict:
    """Inject service-level metadata into every log record.

    Uses setdefault so callers can still override these fields if needed.
    The signature (logger, method, event_dict) is required by the structlog
    processor protocol.
    """
    event_dict.setdefault("service", _settings.app_name)
    event_dict.setdefault("env", _settings.environment)
    return event_dict


def _add_timestamp(
    logger: WrappedLogger, method: str, event_dict: EventDict
) -> EventDict:
    """Stamp every log record with a UTC ISO-8601 timestamp.

    time.gmtime() returns UTC; strftime formats it as "2024-01-15T12:34:56Z".
    Using time.strftime (stdlib) avoids a datetime import and is slightly
    faster than datetime.utcnow().isoformat().
    """
    event_dict["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return event_dict


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def configure_logging() -> None:
    """Configure structlog and Python stdlib logging.  Call once at startup.

    The setup works in two layers so that both structlog loggers and ordinary
    stdlib loggers (used by uvicorn, sqlalchemy, httpx, etc.) produce output
    in the same format:

    1. structlog is configured with the shared_processors chain.  The final
       processor ``wrap_for_formatter`` packages the event_dict so that stdlib
       can receive it.
    2. A ``ProcessorFormatter`` is attached to the root stdlib handler.  Its
       ``foreign_pre_chain`` applies the same processors to records that arrive
       from libraries that never touch structlog directly.
    3. ``cache_logger_on_first_use=True`` freezes the processor chain after the
       first call to get_logger(), giving a measurable performance improvement
       in hot paths.
    """
    log_level = getattr(logging, _settings.log_level.upper(), logging.INFO)

    # Processors applied to every record, regardless of origin.
    # Order matters: context vars are merged first so later processors can see them.
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,    # thread-local context (e.g. request-id)
        structlog.stdlib.add_log_level,             # adds "level": "info" etc.
        _add_service_info,                          # adds "service" and "env"
        _add_timestamp,                             # adds "timestamp"
        structlog.stdlib.PositionalArgumentsFormatter(),  # expand %s-style args
        structlog.processors.StackInfoRenderer(),   # render stack_info kwarg
        structlog.processors.format_exc_info,       # render exc_info as string
    ]

    # Choose the final renderer based on the LOG_FORMAT setting.
    if _settings.log_format == "json":
        # Production: machine-parseable JSON (one object per line)
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        # Development: coloured, human-readable console output
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    # Wire structlog itself (used by get_logger callers)
    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,  # freeze processor chain after first use for speed
    )

    # Attach ProcessorFormatter to the root stdlib handler so third-party
    # library logs also pass through the shared_processors chain.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,  # applied to non-structlog records
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,  # strip internal metadata
            renderer,  # final serialisation step
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Replace any existing handlers on the root logger with our single handler.
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)

    # Silence noisy third-party loggers — they'd flood the output otherwise.
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger for the given module name."""
    return structlog.get_logger(name)
