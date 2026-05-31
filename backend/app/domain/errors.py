"""
Domain exception hierarchy.

All exceptions raised by the service and repository layers are defined here.
The API layer catches these specific types and maps them to HTTP responses —
no message inspection required.

Mapping to HTTP status codes (APPLICATION_SERVICE_ARCHITECTURE.md Part 16.1):
    NotFoundError                → 404
    DomainError                  → 422
    CalculationValidationFailure → 422  (structured field-level errors)
    CalculationError             → 500  (sanitised engine failure)
    ConfigurationNotFoundError   → 500  (data integrity — should never occur)
    PersistenceIntegrityError    → 500  (data integrity — should never occur)
    UnauthorisedAdminError       → 403  (authenticated but insufficient role)

Only stdlib imports. No application dependencies.
"""

from __future__ import annotations

import uuid

from app.engine.contracts import ValidationError, ValidationWarning


class NotFoundError(Exception):
    """
    Raised when a requested entity does not exist or belongs to a different user.

    Both cases produce the same error. Distinguishing them would disclose
    whether a resource exists to an unauthorised caller (AUTHORIZATION_MODEL.md
    Part 2.3 — non-disclosure of existence).

    Maps to HTTP 404.

    Usage:
        raise NotFoundError(entity="deal", id=deal_id)
    """

    def __init__(self, entity: str, id: uuid.UUID) -> None:
        self.entity = entity
        self.id = id
        super().__init__(f"{entity} not found: {id}")


class DomainError(Exception):
    """
    Raised when a domain invariant or business rule is violated.

    Used for invalid state transitions, constraint violations, and any
    domain operation that cannot proceed given current entity state.

    Distinct from CalculationValidationFailure — DomainError is a service
    or entity-level rule, not an engine validation failure.

    Maps to HTTP 422.

    Usage:
        raise DomainError("Cannot update inputs on an archived deal")
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class CalculationValidationFailure(Exception):
    """
    Raised when the engine returns a ValidationResult with is_valid = False.

    Carries the structured list of hard validation errors and any warnings
    produced by the validation pipeline. The API layer serialises these as
    a field_errors list for the frontend to map to specific form fields.

    hard_errors is list[ValidationError] and warnings is
    list[ValidationWarning] from app.engine.contracts.

    Maps to HTTP 422.

    Usage:
        raise CalculationValidationFailure(
            hard_errors=result.hard_errors,
            warnings=result.warnings,
        )
    """

    def __init__(self, hard_errors: list[ValidationError], warnings: list[ValidationWarning]) -> None:
        self.hard_errors = hard_errors
        self.warnings = warnings
        count = len(hard_errors)
        super().__init__(f"Calculation validation failed with {count} error(s)")


class CalculationError(Exception):
    """
    Raised when the engine returns an EngineError (unexpected engine failure).

    The message must always be sanitised before this exception is constructed.
    Internal error detail (error codes, stack traces) is logged server-side
    and must never appear in the message stored here.

    Maps to HTTP 500.

    Usage:
        raise CalculationError(message="Calculation could not be completed.")
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ConfigurationNotFoundError(Exception):
    """
    Raised when active configuration cannot be found for a given date, or when
    a specific configuration version referenced by a snapshot does not exist.

    The second case indicates data integrity corruption — a snapshot references
    a configuration version that has been removed, which should never happen
    given the append-only constraint on configuration tables.

    Maps to HTTP 500. This error reaching the API layer is a critical
    operational issue (OBSERVABILITY_ARCHITECTURE.md Part 17.3).

    Usage:
        raise ConfigurationNotFoundError(config_type="sdlt")
        raise ConfigurationNotFoundError(config_type="assumption", version_id=vid)
    """

    def __init__(
        self,
        config_type: str,
        version_id: uuid.UUID | None = None,
    ) -> None:
        self.config_type = config_type
        self.version_id = version_id
        if version_id is not None:
            msg = f"Configuration not found: {config_type} version {version_id}"
        else:
            msg = f"No active configuration found for type: {config_type}"
        super().__init__(msg)


class PersistenceIntegrityError(Exception):
    """
    Raised by the repository layer when a data integrity constraint is violated.

    Examples:
        - A snapshot root record exists but a required sub-table row is missing
        - A Decimal column returned a float value from the ORM
        - A unique constraint violation that should never occur given the
          application's write patterns

    Maps to HTTP 500. Any instance of this error is a CATEGORY 1 TRUST ERROR
    (OBSERVABILITY_ARCHITECTURE.md Part 13.1) requiring immediate investigation.

    Usage:
        raise PersistenceIntegrityError(
            "snapshot_inputs row missing for snapshot {snapshot_id}"
        )
    """

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class UnauthorisedAdminError(Exception):
    """
    Raised when an authenticated user attempts an admin-only operation without
    admin status.

    This is the only context in which HTTP 403 is the correct response.
    For user-owned resource access by non-owners, NotFoundError (404) is
    used instead to avoid disclosing resource existence.

    Maps to HTTP 403.

    Architecture: AUTHORIZATION_MODEL.md Part 2.3 and Part 7.3.
    """
