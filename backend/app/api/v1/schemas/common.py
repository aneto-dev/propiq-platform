"""
Common Pydantic v2 base types and shared schema primitives.

MoneyStr and RateStr are string-typed aliases used for all monetary and
rate fields in API responses, preventing JSON float precision loss.

All monetary values in API responses are GBP strings with 2dp:
    "-331.90", "11400.00", "60000.00"

All rate/percentage values are also strings:
    "75.00", "5.70", "132.86"

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 15.
    IMPLEMENTATION_ROADMAP.md Commit 6.2.
"""

from __future__ import annotations

from pydantic import BaseModel

# Type aliases — document intent at call sites
MoneyStr = str   # GBP monetary amount as decimal string, e.g. "-331.90"
RateStr = str    # Percentage as decimal string, e.g. "75.00"


class ErrorResponse(BaseModel):
    """Standard error envelope returned for all error HTTP responses."""

    detail: str


class FieldError(BaseModel):
    """One engine validation error, used in CalculationValidationFailureResponse."""

    rule_code: str
    field: str
    message: str
