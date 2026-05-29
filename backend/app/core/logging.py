"""
Structured logging configuration using structlog.

Production: JSON output to stdout. Railway aggregates this.
Development: Colourised console output for readability.

Base fields on every log entry (OBSERVABILITY_ARCHITECTURE.md Part 3.1):
    timestamp, level, service, environment, version, event, message

The `correlation_id` field is added per-request by middleware (Commit 6.6).
It is NOT set here — it flows through contextvars at request time.

Architecture: OBSERVABILITY_ARCHITECTURE.md Part 1.4 — structured logging
is mandatory. Free-text log lines are not acceptable in production.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from app.core.config import get_settings


def _add_base_fields(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Add platform-level fields to every log entry.

    These fields are defined in OBSERVABILITY_ARCHITECTURE.md Part 3.1
    as required base fields present on every log line.
    """
    settings = get_settings()
    event_dict["service"] = "propiq-backend"
    event_dict["environment"] = settings.environment
    event_dict["version"] = settings.app_version
    return event_dict


def configure_logging() -> None:
    """
    Configure structlog for the application.

    Called once in create_app() before any logging occurs.
    Calling multiple times is safe — structlog handles reconfiguration.
    """
    settings = get_settings()

    # Common processors applied in every environment.
    # Order matters: each processor receives the output of the previous one.
    shared_processors: list[Any] = [
        # Add log level as a string ("info", "warning", etc.).
        structlog.stdlib.add_log_level,
        # Add ISO-8601 UTC timestamp.
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Add our platform-level base fields.
        _add_base_fields,
        # Render exceptions as structured dicts (not raw tracebacks in JSON).
        structlog.processors.format_exc_info,
        # Ensure all values are JSON-serialisable.
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.is_production or settings.environment == "staging":
        # Production/staging: render as JSON for log aggregation.
        # OBSERVABILITY_ARCHITECTURE.md Part 2.2: structured JSON to stdout.
        renderer = structlog.processors.JSONRenderer()
    else:
        # Development: colourised console output for human readability.
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [renderer],
        # Use stdlib logging as the underlying logger so that third-party
        # libraries (SQLAlchemy, uvicorn) also appear in structlog output.
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to route through structlog so uvicorn,
    # SQLAlchemy, and alembic log entries appear in the same format.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """
    Return a structlog logger bound to the calling module's name.

    Usage:
        logger = get_logger(__name__)
        logger.info("deal.created", deal_id=str(deal_id), user_id=str(user_id))

    The `event` kwarg corresponds to the dot-separated event taxonomy defined
    in OBSERVABILITY_ARCHITECTURE.md Part 3.2.
    """
    return structlog.get_logger(name)
