"""
Correlation ID middleware and structured request logging.

Assigns a unique correlation ID to every incoming request and propagates it
through the structlog context so that every log entry within the request
lifetime carries the same ID.

Behaviour (OBSERVABILITY_ARCHITECTURE.md Part 4.2):
  - If the client supplies X-Correlation-ID:
      - accept if it is a bare UUID4 (returned as req_<uuid>)
      - accept if it is already a req_<uuid> string (returned unchanged)
      - otherwise generate a fresh req_<uuid4>
  - Never return HTTP 400 for a malformed X-Correlation-ID header.
  - Bind correlation_id to structlog context for the request lifetime.
  - Echo correlation_id as X-Correlation-ID on every response.
  - Log api.request.received (before processing) and
    api.request.completed (after processing, with status_code and duration_ms).

Architecture:
    OBSERVABILITY_ARCHITECTURE.md Part 4 — correlation ID strategy.
    IMPLEMENTATION_ROADMAP.md Commit 6.6.
"""

from __future__ import annotations

import re
import time
import uuid

import structlog
import structlog.contextvars
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Correlation ID format
# ---------------------------------------------------------------------------

# UUID v4 pattern (case-insensitive, with or without hyphens — we normalise)
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _resolve_correlation_id(client_header: str) -> str:
    """
    Derive the request's correlation ID from the client-supplied header value.

    Acceptance rules:
      - "req_<uuid4>"  — already in canonical form; accepted unchanged
      - "<uuid4>"      — bare UUID; normalised to "req_<uuid>"
      - anything else  — generate a fresh "req_<uuid4>"

    Never raises. Never returns a 400. An invalid header silently falls back
    to a generated ID.

    Architecture: OBSERVABILITY_ARCHITECTURE.md §4.2.
    """
    if client_header:
        # Already canonical: req_<uuid>
        if client_header.startswith("req_") and _UUID_RE.match(client_header[4:]):
            return client_header
        # Bare UUID: normalise to req_<uuid>
        if _UUID_RE.match(client_header):
            return f"req_{client_header.lower()}"
    # Generate fresh ID
    return f"req_{uuid.uuid4()}"


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Starlette ASGI middleware that assigns and propagates a correlation ID.

    Runs around every request. Sets the structlog context, logs the request
    lifecycle events, and echoes the ID in the response header.

    Architecture: OBSERVABILITY_ARCHITECTURE.md Part 4.2, Part 2.3.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Clear any stale context from a previous request in this worker.
        # This must run before bind_contextvars to prevent context leakage.
        structlog.contextvars.clear_contextvars()

        # Resolve correlation ID (client-provided or generated)
        client_header = request.headers.get("X-Correlation-ID", "")
        correlation_id = _resolve_correlation_id(client_header)

        # Bind to structlog context — all log entries within this request
        # will automatically include correlation_id via merge_contextvars.
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        # Log request receipt.
        # OBSERVABILITY_ARCHITECTURE.md §2.3: method, path, correlation_id.
        # user_id is not available at middleware level (auth not yet resolved).
        logger.info(
            "api.request.received",
            method=request.method,
            path=request.url.path,
        )

        # Process the request and measure wall-clock duration.
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000)

        # Log request completion.
        # OBSERVABILITY_ARCHITECTURE.md §2.3: status_code, duration_ms, correlation_id.
        logger.info(
            "api.request.completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        # Echo the correlation ID to the client for client-side tracing.
        # Phase 6 exit criterion: X-Correlation-ID present on all responses.
        response.headers["X-Correlation-ID"] = correlation_id

        return response


# ---------------------------------------------------------------------------
# Registration helper — mirrors register_error_handlers(app) pattern
# ---------------------------------------------------------------------------


def register_middleware(app: FastAPI) -> None:
    """
    Register all API middleware on the FastAPI application.

    Called from create_app() after error handlers are registered.
    Middleware is processed in LIFO order by Starlette; CorrelationIdMiddleware
    is the outermost wrapper so the correlation ID is set before any other
    processing, including exception handlers.

    Architecture: IMPLEMENTATION_ROADMAP.md Commit 6.6.
    """
    app.add_middleware(CorrelationIdMiddleware)
