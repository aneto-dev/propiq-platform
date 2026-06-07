"""
Global FastAPI exception handlers — domain error → HTTP response mapping.

Maps every domain exception to the correct HTTP status code and a structured
JSON body. Registered on the FastAPI application in app/main.py via
register_error_handlers(app).

Mappings (APPLICATION_SERVICE_ARCHITECTURE.md Part 16.1):
    NotFoundError                → 404
    DomainError                  → 422
    CalculationValidationFailure → 422  (structured field_errors list)
    CalculationError             → 500  (sanitised engine failure)
    UnauthorisedAdminError       → 403
    ConfigurationNotFoundError   → 500  (data integrity — should never occur)
    Exception (catch-all)        → 500  (generic; detail suppressed in production)

All responses use a consistent JSON envelope:
    {"detail": "<human-readable message>"}

CalculationValidationFailure adds a `field_errors` array for frontend mapping.

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 16.
    IMPLEMENTATION_ROADMAP.md Commit 6.2.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.errors import (
    CalculationError,
    CalculationValidationFailure,
    ConfigurationNotFoundError,
    DomainError,
    NotFoundError,
    UnauthorisedAdminError,
)


def register_error_handlers(app: FastAPI) -> None:
    """
    Register all domain exception handlers on the FastAPI application.

    Called from create_app() in app/main.py.
    """

    @app.exception_handler(NotFoundError)
    async def not_found_handler(
        request: Request, exc: NotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": f"{exc.entity} not found"},
        )

    @app.exception_handler(DomainError)
    async def domain_error_handler(
        request: Request, exc: DomainError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": exc.message},
        )

    @app.exception_handler(CalculationValidationFailure)
    async def calculation_validation_handler(
        request: Request, exc: CalculationValidationFailure
    ) -> JSONResponse:
        """
        Returns structured field_errors for the frontend to map to form fields.
        Each error includes rule_code, field, and message.
        """
        field_errors = [
            {
                "rule_code": e.rule_code,
                "field": e.field,
                "message": e.message,
            }
            for e in exc.hard_errors
        ]
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Calculation validation failed",
                "field_errors": field_errors,
            },
        )

    @app.exception_handler(CalculationError)
    async def calculation_error_handler(
        request: Request, exc: CalculationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": exc.message},
        )

    @app.exception_handler(UnauthorisedAdminError)
    async def unauthorised_admin_handler(
        request: Request, exc: UnauthorisedAdminError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"detail": "Admin access required"},
        )

    @app.exception_handler(ConfigurationNotFoundError)
    async def configuration_not_found_handler(
        request: Request, exc: ConfigurationNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": "Configuration data error — contact support"},
        )

    @app.exception_handler(Exception)
    async def generic_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """
        Catch-all for any unhandled exception.
        Returns 500 with a generic message — no internal detail exposed.
        """
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred"},
        )
