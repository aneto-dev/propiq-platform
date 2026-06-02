"""
Validation pipeline — V-01 through V-25 as declarative rule data.

All 25 rules are defined as a list of ValidationRule objects.
The pipeline runner iterates every rule and collects all failures.
It never stops at the first error.

Architecture principles (ENGINE_ARCHITECTURE.md Part 5):
    - Validation rules are data, not conditionals.
    - New rules are added to the list, not to control flow.
    - The complete rule set is inspectable as data at runtime.

V-14 note: LLP ownership structure cannot be constructed from the
OwnershipStructure enum. The type system prevents it from reaching
the engine. V-14 is implemented as a value-level guard for any
ownership_structure value outside the supported set, per Option A
confirmed during Commit 2.6 planning.

Source: CALCULATION_SPEC.md — Validation Rules.
ENGINE_CONTRACTS.md — ValidationResult, ValidationError, ValidationWarning.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.domain.enums import OwnershipStructure, Tenure
from app.engine.contracts import (
    EngineInput,
    ValidationError,
    ValidationResult,
    ValidationWarning,
)

# ---------------------------------------------------------------------------
# ValidationRule data type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationRule:
    """
    A single declarative validation rule.

    condition: callable that receives EngineInput and returns True when the
               rule is violated (i.e. True = trigger the rule).
    severity:  "HARD" blocks calculation; "WARN" carries forward.
    """

    code: str
    field: str
    severity: Literal["HARD", "WARN"]
    condition: Callable[[EngineInput], bool]
    message: str


# ---------------------------------------------------------------------------
# Supported ownership structures — used by V-14 guard
# ---------------------------------------------------------------------------

_SUPPORTED_OWNERSHIP_STRUCTURES: frozenset[str] = frozenset(
    v.value for v in OwnershipStructure
)


# ---------------------------------------------------------------------------
# Validation rules — V-01 through V-25
# Order follows CALCULATION_SPEC.md table.
# ---------------------------------------------------------------------------

VALIDATION_RULES: list[ValidationRule] = [
    # ------------------------------------------------------------------
    # V-01: purchase_price must be > 0
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-01",
        field="purchase_price",
        severity="HARD",
        condition=lambda i: i.purchase_price <= Decimal("0"),
        message="Purchase price must be greater than zero.",
    ),
    # ------------------------------------------------------------------
    # V-02: purchase_price < 10,000 is unusually low (WARN)
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-02",
        field="purchase_price",
        severity="WARN",
        condition=lambda i: i.purchase_price < Decimal("10000"),
        message="Purchase price is unusually low. Please verify.",
    ),
    # ------------------------------------------------------------------
    # V-03: purchase_price > 10,000,000 is unusually high (WARN)
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-03",
        field="purchase_price",
        severity="WARN",
        condition=lambda i: i.purchase_price > Decimal("10000000"),
        message="Purchase price is unusually high. Please verify.",
    ),
    # ------------------------------------------------------------------
    # V-04: monthly_rent must be > 0
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-04",
        field="monthly_rent",
        severity="HARD",
        condition=lambda i: i.monthly_rent <= Decimal("0"),
        message="Monthly rent estimate must be greater than zero.",
    ),
    # ------------------------------------------------------------------
    # V-05: deposit_amount must be > 0
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-05",
        field="deposit_amount",
        severity="HARD",
        condition=lambda i: i.deposit_amount <= Decimal("0"),
        message="Deposit amount must be greater than zero.",
    ),
    # ------------------------------------------------------------------
    # V-06: deposit cannot equal or exceed purchase price
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-06",
        field="deposit_amount",
        severity="HARD",
        condition=lambda i: i.deposit_amount >= i.purchase_price,
        message="Deposit cannot equal or exceed the purchase price.",
    ),
    # ------------------------------------------------------------------
    # V-07: deposit below 15% of purchase price (HARD)
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-07",
        field="deposit_amount",
        severity="HARD",
        condition=lambda i: (
            i.purchase_price > Decimal("0")
            and i.deposit_amount < i.purchase_price * Decimal("0.15")
        ),
        message=(
            "Deposit is below 15% of the purchase price. "
            "BTL mortgages are not available below this threshold."
        ),
    ),
    # ------------------------------------------------------------------
    # V-08: deposit below 25% of purchase price (WARN)
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-08",
        field="deposit_amount",
        severity="WARN",
        condition=lambda i: (
            i.purchase_price > Decimal("0")
            and i.deposit_amount < i.purchase_price * Decimal("0.25")
        ),
        message=(
            "Deposit is below 25%. Most BTL lenders require a minimum "
            "25% deposit. Product availability may be limited."
        ),
    ),
    # ------------------------------------------------------------------
    # V-09: mortgage_interest_rate cannot be negative
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-09",
        field="mortgage_interest_rate",
        severity="HARD",
        condition=lambda i: i.mortgage_interest_rate < Decimal("0"),
        message="Mortgage interest rate cannot be negative.",
    ),
    # ------------------------------------------------------------------
    # V-10: rate = 0 means cash purchase (WARN)
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-10",
        field="mortgage_interest_rate",
        severity="WARN",
        condition=lambda i: i.mortgage_interest_rate == Decimal("0"),
        message=(
            "Interest rate is zero. This will be treated as a cash purchase. "
            "Mortgage calculations will not apply."
        ),
    ),
    # ------------------------------------------------------------------
    # V-11: rate > 0 and < 3.0 is unusually low (WARN)
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-11",
        field="mortgage_interest_rate",
        severity="WARN",
        condition=lambda i: (
            Decimal("0") < i.mortgage_interest_rate < Decimal("3.0")
        ),
        message="Interest rate is unusually low for a BTL mortgage. Please verify.",
    ),
    # ------------------------------------------------------------------
    # V-12: rate > 10.0 is unusually high (WARN)
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-12",
        field="mortgage_interest_rate",
        severity="WARN",
        condition=lambda i: i.mortgage_interest_rate > Decimal("10.0"),
        message="Interest rate is unusually high. Please verify.",
    ),
    # ------------------------------------------------------------------
    # V-13: mortgage term must be 5–35 years
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-13",
        field="mortgage_term_years",
        severity="HARD",
        condition=lambda i: (
            i.mortgage_term_years < 5 or i.mortgage_term_years > 35
        ),
        message="Mortgage term must be between 5 and 35 years.",
    ),
    # ------------------------------------------------------------------
    # V-14: unsupported ownership structure guard
    # LLP cannot be constructed from OwnershipStructure — this rule
    # guards against any future value outside the supported set.
    # Option A: check against the supported value set, not a hardcoded
    # "LLP" string. Currently unreachable given the enum definition but
    # present as a structural protection layer (ENGINE_ARCHITECTURE.md).
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-14",
        field="ownership_structure",
        severity="HARD",
        condition=lambda i: (
            i.ownership_structure.value
            not in _SUPPORTED_OWNERSHIP_STRUCTURES
        ),
        message="LLP ownership structure is not supported in v1.0.",
    ),
    # ------------------------------------------------------------------
    # V-15: only RESIDENTIAL_SINGLE_LET supported in v1.0
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-15",
        field="property_type",
        severity="HARD",
        condition=lambda i: (
            i.property_type.value != "RESIDENTIAL_SINGLE_LET"
        ),
        message="Only residential single-let properties are supported in v1.0.",
    ),
    # ------------------------------------------------------------------
    # V-16: only England supported in v1.0
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-16",
        field="property_country",
        severity="HARD",
        condition=lambda i: i.property_country.value != "ENGLAND",
        message=(
            "Only England is supported in v1.0. Scotland, Wales, and "
            "Northern Ireland use different transaction tax regimes."
        ),
    ),
    # ------------------------------------------------------------------
    # V-17: income_tax_band required for INDIVIDUAL
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-17",
        field="income_tax_band",
        severity="HARD",
        condition=lambda i: (
            i.ownership_structure == OwnershipStructure.INDIVIDUAL
            and i.income_tax_band is None
        ),
        message="Income tax band is required for individual ownership.",
    ),
    # ------------------------------------------------------------------
    # V-18: void rate must be 0–100
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-18",
        field="void_rate_percent",
        severity="HARD",
        condition=lambda i: (
            i.void_rate_percent < Decimal("0")
            or i.void_rate_percent > Decimal("100")
        ),
        message="Void rate must be between 0% and 100%.",
    ),
    # ------------------------------------------------------------------
    # V-19: void rate = 0 is suspicious (WARN)
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-19",
        field="void_rate_percent",
        severity="WARN",
        condition=lambda i: i.void_rate_percent == Decimal("0"),
        message=(
            "Void rate is set to zero. Consider whether this is realistic "
            "— most properties experience some vacancy between tenancies."
        ),
    ),
    # ------------------------------------------------------------------
    # V-20: letting agent fee > 25% is unusually high (WARN)
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-20",
        field="letting_agent_fee_percent",
        severity="WARN",
        condition=lambda i: i.letting_agent_fee_percent > Decimal("25"),
        message="Letting agent fee above 25% is unusually high. Please verify.",
    ),
    # ------------------------------------------------------------------
    # V-21: leasehold requires service charge (may be 0, not null)
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-21",
        field="annual_service_charge",
        severity="HARD",
        condition=lambda i: (
            i.tenure == Tenure.LEASEHOLD
            and i.annual_service_charge is None
        ),
        message=(
            "Annual service charge must be provided for leasehold properties. "
            "Enter 0 if genuinely not applicable."
        ),
    ),
    # ------------------------------------------------------------------
    # V-22: leasehold requires ground rent (may be 0, not null)
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-22",
        field="annual_ground_rent",
        severity="HARD",
        condition=lambda i: (
            i.tenure == Tenure.LEASEHOLD
            and i.annual_ground_rent is None
        ),
        message=(
            "Annual ground rent must be provided for leasehold properties. "
            "Enter 0 if genuinely not applicable."
        ),
    ),
    # ------------------------------------------------------------------
    # V-23: ground rent > £250 on leasehold may affect mortgageability (WARN)
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-23",
        field="annual_ground_rent",
        severity="WARN",
        condition=lambda i: (
            i.tenure == Tenure.LEASEHOLD
            and i.annual_ground_rent is not None
            and i.annual_ground_rent > Decimal("250")
        ),
        message=(
            "Ground rent above £250/year. Pre-2022 leases above this threshold "
            "may affect mortgage availability. Take legal advice."
        ),
    ),
    # ------------------------------------------------------------------
    # V-24: maintenance reserve > 5% is unusually high (WARN)
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-24",
        field="maintenance_reserve_percent",
        severity="WARN",
        condition=lambda i: i.maintenance_reserve_percent > Decimal("5.0"),
        message=(
            "Maintenance reserve above 5% of purchase price is unusually high. "
            "Please verify."
        ),
    ),
    # ------------------------------------------------------------------
    # V-25: refurbishment cost = 0 (WARN — may be intentional)
    # ------------------------------------------------------------------
    ValidationRule(
        code="V-25",
        field="refurbishment_cost",
        severity="WARN",
        condition=lambda i: i.refurbishment_cost == Decimal("0"),
        message=(
            "No refurbishment cost entered. If works are required before "
            "letting, ensure this is accounted for."
        ),
    ),
]


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------


def run_validation(engine_input: EngineInput) -> ValidationResult:
    """
    Run all validation rules against EngineInput.

    Iterates every rule in VALIDATION_RULES and collects all failures.
    Never stops at the first error — all rules are evaluated.

    Returns a ValidationResult:
        is_valid = False  if any HARD rule triggered
        is_valid = True   if only WARN rules triggered (or none)
        hard_errors       list of ValidationError for each HARD failure
        warnings          list of ValidationWarning for each WARN failure

    Source: ENGINE_ARCHITECTURE.md Part 5.
    """
    hard_errors: list[ValidationError] = []
    warnings: list[ValidationWarning] = []

    for rule in VALIDATION_RULES:
        if rule.condition(engine_input):
            if rule.severity == "HARD":
                hard_errors.append(
                    ValidationError(
                        rule_code=rule.code,
                        field=rule.field,
                        message=rule.message,
                    )
                )
            else:
                warnings.append(
                    ValidationWarning(
                        rule_code=rule.code,
                        field=rule.field,
                        message=rule.message,
                    )
                )

    return ValidationResult(
        is_valid=len(hard_errors) == 0,
        hard_errors=hard_errors,
        warnings=warnings,
    )
