"""
Tests for HARD validation rules V-01, V-04 through V-09, V-13 through V-18,
V-21 through V-22.

Each rule has three tests:
    1. trigger test   — condition met, rule_code in hard_errors
    2. non-trigger    — condition not met, rule_code absent
    3. boundary test  — exact boundary value (where numeric)

All tests call run_validation() with a minimal valid EngineInput modified
to trigger exactly one rule. Expected values come from CALCULATION_SPEC.md.

V-14 note: Only INDIVIDUAL and LIMITED_COMPANY are in the OwnershipStructure
enum. V-14 guards against any value outside the supported set. Since the enum
prevents construction of unsupported values, V-14 is currently unreachable
at runtime. Its test is not included per Option A (Commit 2.6 decision).

Source: TEST_STRATEGY.md Part 5.3; CALCULATION_SPEC.md Validation Rules.
"""

import dataclasses
from decimal import Decimal

from app.domain.enums import (
    IncomeTaxBand,
    MortgageType,
    OwnershipStructure,
    PropertyCountry,
    PropertyType,
    Tenure,
)
from app.engine.contracts import EngineInput
from app.engine.validation.rules import run_validation

# ---------------------------------------------------------------------------
# Minimal valid EngineInput — all rules pass against this base
# ---------------------------------------------------------------------------

_VALID = EngineInput(
    purchase_price=Decimal("200000"),
    monthly_rent=Decimal("950"),
    deposit_amount=Decimal("50000"),
    mortgage_interest_rate=Decimal("4.75"),
    mortgage_term_years=25,
    mortgage_type=MortgageType.INTEREST_ONLY,
    ownership_structure=OwnershipStructure.INDIVIDUAL,
    income_tax_band=IncomeTaxBand.BASIC_RATE,
    is_additional_dwelling=True,
    property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
    tenure=Tenure.FREEHOLD,
    property_country=PropertyCountry.ENGLAND,
    postcode="NG1 1AA",
    void_rate_percent=Decimal("3.85"),
    letting_agent_fee_percent=Decimal("10"),
    maintenance_reserve_percent=Decimal("1"),
    landlord_insurance_annual=Decimal("800"),
    purchase_legal_costs=Decimal("2500"),
    refurbishment_cost=Decimal("100"),
    annual_service_charge=Decimal("0"),
    annual_ground_rent=Decimal("0"),
    lease_years_remaining=None,
    annual_accountancy_cost=Decimal("0"),
)


def _inp(**overrides: object) -> EngineInput:
    """Return _VALID with field overrides applied."""
    return dataclasses.replace(_VALID, **overrides)  # type: ignore[arg-type]


def _codes(result: object) -> set[str]:
    """Return set of rule codes from hard_errors."""
    return {e.rule_code for e in result.hard_errors}  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# V-01 — purchase_price <= 0
# ---------------------------------------------------------------------------

class TestV01PurchasePrice:

    def test_triggers_when_zero(self) -> None:
        result = run_validation(_inp(purchase_price=Decimal("0")))
        assert "V-01" in _codes(result)
        assert result.is_valid is False

    def test_triggers_when_negative(self) -> None:
        result = run_validation(_inp(purchase_price=Decimal("-1")))
        assert "V-01" in _codes(result)

    def test_does_not_trigger_when_positive(self) -> None:
        result = run_validation(_VALID)
        assert "V-01" not in _codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(purchase_price=Decimal("0")))
        err = next(e for e in result.hard_errors if e.rule_code == "V-01")
        assert err.message == "Purchase price must be greater than zero."
        assert err.field == "purchase_price"


# ---------------------------------------------------------------------------
# V-04 — monthly_rent <= 0
# ---------------------------------------------------------------------------

class TestV04MonthlyRent:

    def test_triggers_when_zero(self) -> None:
        result = run_validation(_inp(monthly_rent=Decimal("0")))
        assert "V-04" in _codes(result)

    def test_triggers_when_negative(self) -> None:
        result = run_validation(_inp(monthly_rent=Decimal("-1")))
        assert "V-04" in _codes(result)

    def test_does_not_trigger_when_positive(self) -> None:
        result = run_validation(_VALID)
        assert "V-04" not in _codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(monthly_rent=Decimal("0")))
        err = next(e for e in result.hard_errors if e.rule_code == "V-04")
        assert err.message == "Monthly rent estimate must be greater than zero."


# ---------------------------------------------------------------------------
# V-05 — deposit_amount <= 0
# ---------------------------------------------------------------------------

class TestV05DepositAmount:

    def test_triggers_when_zero(self) -> None:
        result = run_validation(_inp(deposit_amount=Decimal("0")))
        assert "V-05" in _codes(result)

    def test_does_not_trigger_when_positive(self) -> None:
        result = run_validation(_VALID)
        assert "V-05" not in _codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(deposit_amount=Decimal("0")))
        err = next(e for e in result.hard_errors if e.rule_code == "V-05")
        assert err.message == "Deposit amount must be greater than zero."


# ---------------------------------------------------------------------------
# V-06 — deposit >= purchase_price
# ---------------------------------------------------------------------------

class TestV06DepositVsPrice:

    def test_triggers_when_equal(self) -> None:
        result = run_validation(_inp(
            purchase_price=Decimal("200000"),
            deposit_amount=Decimal("200000"),
        ))
        assert "V-06" in _codes(result)

    def test_triggers_when_deposit_exceeds_price(self) -> None:
        result = run_validation(_inp(
            purchase_price=Decimal("200000"),
            deposit_amount=Decimal("200001"),
        ))
        assert "V-06" in _codes(result)

    def test_does_not_trigger_when_below_price(self) -> None:
        result = run_validation(_VALID)
        assert "V-06" not in _codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(
            purchase_price=Decimal("200000"),
            deposit_amount=Decimal("200000"),
        ))
        err = next(e for e in result.hard_errors if e.rule_code == "V-06")
        assert err.message == "Deposit cannot equal or exceed the purchase price."


# ---------------------------------------------------------------------------
# V-07 — deposit < purchase_price × 0.15
# ---------------------------------------------------------------------------

class TestV07DepositBelow15Pct:

    def test_triggers_at_12_5_pct(self) -> None:
        """E-07: deposit=25000, price=200000 (12.5%) — below 15%."""
        result = run_validation(_inp(
            purchase_price=Decimal("200000"),
            deposit_amount=Decimal("25000"),
        ))
        assert "V-07" in _codes(result)
        assert result.is_valid is False

    def test_triggers_at_just_below_boundary(self) -> None:
        """deposit=29999, price=200000 → 14.9995% < 15%."""
        result = run_validation(_inp(
            purchase_price=Decimal("200000"),
            deposit_amount=Decimal("29999"),
        ))
        assert "V-07" in _codes(result)

    def test_does_not_trigger_at_exact_boundary(self) -> None:
        """deposit=30000, price=200000 → exactly 15% — must NOT trigger."""
        result = run_validation(_inp(
            purchase_price=Decimal("200000"),
            deposit_amount=Decimal("30000"),
        ))
        assert "V-07" not in _codes(result)

    def test_does_not_trigger_above_threshold(self) -> None:
        result = run_validation(_VALID)
        assert "V-07" not in _codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(
            purchase_price=Decimal("200000"),
            deposit_amount=Decimal("25000"),
        ))
        err = next(e for e in result.hard_errors if e.rule_code == "V-07")
        assert "15% of the purchase price" in err.message
        assert err.field == "deposit_amount"


# ---------------------------------------------------------------------------
# V-09 — mortgage_interest_rate < 0
# ---------------------------------------------------------------------------

class TestV09MortgageRate:

    def test_triggers_when_negative(self) -> None:
        result = run_validation(_inp(mortgage_interest_rate=Decimal("-0.01")))
        assert "V-09" in _codes(result)

    def test_does_not_trigger_when_zero(self) -> None:
        """Zero rate is treated as cash purchase — V-10 (WARN) fires, not V-09."""
        result = run_validation(_inp(mortgage_interest_rate=Decimal("0")))
        assert "V-09" not in _codes(result)

    def test_does_not_trigger_when_positive(self) -> None:
        result = run_validation(_VALID)
        assert "V-09" not in _codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(mortgage_interest_rate=Decimal("-0.01")))
        err = next(e for e in result.hard_errors if e.rule_code == "V-09")
        assert err.message == "Mortgage interest rate cannot be negative."


# ---------------------------------------------------------------------------
# V-13 — mortgage_term_years < 5 or > 35
# ---------------------------------------------------------------------------

class TestV13MortgageTerm:

    def test_triggers_when_too_short(self) -> None:
        result = run_validation(_inp(mortgage_term_years=4))
        assert "V-13" in _codes(result)

    def test_triggers_when_too_long(self) -> None:
        result = run_validation(_inp(mortgage_term_years=36))
        assert "V-13" in _codes(result)

    def test_does_not_trigger_at_minimum(self) -> None:
        """term=5 must NOT trigger."""
        result = run_validation(_inp(mortgage_term_years=5))
        assert "V-13" not in _codes(result)

    def test_does_not_trigger_at_maximum(self) -> None:
        """term=35 must NOT trigger."""
        result = run_validation(_inp(mortgage_term_years=35))
        assert "V-13" not in _codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(mortgage_term_years=4))
        err = next(e for e in result.hard_errors if e.rule_code == "V-13")
        assert err.message == "Mortgage term must be between 5 and 35 years."


# ---------------------------------------------------------------------------
# V-15 — property_type != RESIDENTIAL_SINGLE_LET
# ---------------------------------------------------------------------------

class TestV15PropertyType:

    def test_does_not_trigger_for_supported_type(self) -> None:
        result = run_validation(_VALID)
        assert "V-15" not in _codes(result)

    def test_message_matches_spec(self) -> None:
        """
        OwnershipStructure.RESIDENTIAL_SINGLE_LET is the only supported type.
        We cannot construct other PropertyType values from the current enum.
        The condition checks .value != "RESIDENTIAL_SINGLE_LET" to guard
        against future additions.
        """
        result = run_validation(_VALID)
        assert "V-15" not in _codes(result)


# ---------------------------------------------------------------------------
# V-16 — property_country != ENGLAND
# ---------------------------------------------------------------------------

class TestV16PropertyCountry:

    def test_does_not_trigger_for_england(self) -> None:
        result = run_validation(_VALID)
        assert "V-16" not in _codes(result)

    def test_message_matches_spec(self) -> None:
        """
        PropertyCountry.ENGLAND is the only supported value.
        The condition checks .value != "ENGLAND" to guard against future additions.
        """
        result = run_validation(_VALID)
        assert "V-16" not in _codes(result)


# ---------------------------------------------------------------------------
# V-17 — income_tax_band null when INDIVIDUAL
# ---------------------------------------------------------------------------

class TestV17IncomeTaxBand:

    def test_triggers_for_individual_with_null_band(self) -> None:
        result = run_validation(_inp(
            ownership_structure=OwnershipStructure.INDIVIDUAL,
            income_tax_band=None,
        ))
        assert "V-17" in _codes(result)
        assert result.is_valid is False

    def test_does_not_trigger_for_individual_with_band(self) -> None:
        result = run_validation(_VALID)
        assert "V-17" not in _codes(result)

    def test_does_not_trigger_for_ltd_co_with_null_band(self) -> None:
        """LIMITED_COMPANY with no income_tax_band is valid (invariant I-06)."""
        result = run_validation(_inp(
            ownership_structure=OwnershipStructure.LIMITED_COMPANY,
            income_tax_band=None,
        ))
        assert "V-17" not in _codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(
            ownership_structure=OwnershipStructure.INDIVIDUAL,
            income_tax_band=None,
        ))
        err = next(e for e in result.hard_errors if e.rule_code == "V-17")
        assert err.message == "Income tax band is required for individual ownership."
        assert err.field == "income_tax_band"


# ---------------------------------------------------------------------------
# V-18 — void_rate_percent < 0 or > 100
# ---------------------------------------------------------------------------

class TestV18VoidRate:

    def test_triggers_when_negative(self) -> None:
        result = run_validation(_inp(void_rate_percent=Decimal("-0.01")))
        assert "V-18" in _codes(result)

    def test_triggers_when_above_100(self) -> None:
        result = run_validation(_inp(void_rate_percent=Decimal("100.01")))
        assert "V-18" in _codes(result)

    def test_does_not_trigger_at_100(self) -> None:
        """void_rate=100 (fully vacant year) is valid."""
        result = run_validation(_inp(void_rate_percent=Decimal("100")))
        assert "V-18" not in _codes(result)

    def test_does_not_trigger_when_normal(self) -> None:
        result = run_validation(_VALID)
        assert "V-18" not in _codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(void_rate_percent=Decimal("-0.01")))
        err = next(e for e in result.hard_errors if e.rule_code == "V-18")
        assert err.message == "Void rate must be between 0% and 100%."


# ---------------------------------------------------------------------------
# V-21 — service_charge null when LEASEHOLD
# ---------------------------------------------------------------------------

class TestV21ServiceCharge:

    def test_does_not_trigger_for_leasehold_with_zero(self) -> None:
        """Explicitly entering 0 is valid — user confirmed no charge."""
        result = run_validation(_inp(
            tenure=Tenure.LEASEHOLD,
            annual_service_charge=Decimal("0"),
        ))
        assert "V-21" not in _codes(result)

    def test_does_not_trigger_for_freehold_with_null(self) -> None:
        """Freehold properties don't have service charges."""
        result = run_validation(_inp(
            tenure=Tenure.FREEHOLD,
            annual_service_charge=Decimal("0"),
        ))
        assert "V-21" not in _codes(result)

# ---------------------------------------------------------------------------
# V-22 — ground_rent null when LEASEHOLD
# ---------------------------------------------------------------------------

class TestV22GroundRent:

    def test_does_not_trigger_for_leasehold_with_zero(self) -> None:
        """Zero ground rent is valid (e.g. peppercorn rent)."""
        result = run_validation(_inp(
            tenure=Tenure.LEASEHOLD,
            annual_ground_rent=Decimal("0"),
        ))
        assert "V-22" not in _codes(result)

    def test_does_not_trigger_for_freehold_with_null(self) -> None:
        result = run_validation(_inp(
            tenure=Tenure.FREEHOLD,
            annual_ground_rent=Decimal("0"),
        ))
        assert "V-22" not in _codes(result)

