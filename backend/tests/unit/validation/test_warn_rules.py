"""
Tests for WARN validation rules V-02, V-03, V-08, V-10 through V-12,
V-19, V-20, V-23 through V-25.

WARN rules set is_valid=True. Warnings are carried forward into EngineResult.

Source: TEST_STRATEGY.md Part 5.4; CALCULATION_SPEC.md Validation Rules.
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
# Minimal valid EngineInput
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
    return dataclasses.replace(_VALID, **overrides)  # type: ignore[arg-type]


def _warn_codes(result: object) -> set[str]:
    return {w.rule_code for w in result.warnings}  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# V-02 — purchase_price < 10,000 (WARN)
# ---------------------------------------------------------------------------

class TestV02LowPurchasePrice:

    def test_triggers_at_9999(self) -> None:
        result = run_validation(_inp(
            purchase_price=Decimal("9999"),
            deposit_amount=Decimal("2500"),
        ))
        assert "V-02" in _warn_codes(result)
        assert result.is_valid is True

    def test_does_not_trigger_at_10000(self) -> None:
        """Boundary: 10,000 must NOT trigger."""
        result = run_validation(_inp(
            purchase_price=Decimal("10000"),
            deposit_amount=Decimal("2500"),
        ))
        assert "V-02" not in _warn_codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(
            purchase_price=Decimal("9999"),
            deposit_amount=Decimal("2500"),
        ))
        w = next(w for w in result.warnings if w.rule_code == "V-02")
        assert w.message == "Purchase price is unusually low. Please verify."
        assert w.field == "purchase_price"


# ---------------------------------------------------------------------------
# V-03 — purchase_price > 10,000,000 (WARN)
# ---------------------------------------------------------------------------

class TestV03HighPurchasePrice:

    def test_triggers_at_10_000_001(self) -> None:
        result = run_validation(_inp(
            purchase_price=Decimal("10000001"),
            deposit_amount=Decimal("2500001"),
        ))
        assert "V-03" in _warn_codes(result)
        assert result.is_valid is True

    def test_does_not_trigger_at_10_000_000(self) -> None:
        """Boundary: 10,000,000 must NOT trigger."""
        result = run_validation(_inp(
            purchase_price=Decimal("10000000"),
            deposit_amount=Decimal("2500000"),
        ))
        assert "V-03" not in _warn_codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(
            purchase_price=Decimal("10000001"),
            deposit_amount=Decimal("2500001"),
        ))
        w = next(w for w in result.warnings if w.rule_code == "V-03")
        assert w.message == "Purchase price is unusually high. Please verify."


# ---------------------------------------------------------------------------
# V-08 — deposit < 25% of purchase price (WARN)
# ---------------------------------------------------------------------------

class TestV08DepositBelow25Pct:

    def test_triggers_below_25_pct(self) -> None:
        """E-08: deposit=35000, price=200000 (17.5%)."""
        result = run_validation(_inp(
            purchase_price=Decimal("200000"),
            deposit_amount=Decimal("35000"),
        ))
        assert "V-08" in _warn_codes(result)
        assert result.is_valid is True

    def test_triggers_at_just_below_boundary(self) -> None:
        """deposit=49999, price=200000 → 24.9995% < 25%."""
        result = run_validation(_inp(
            purchase_price=Decimal("200000"),
            deposit_amount=Decimal("49999"),
        ))
        assert "V-08" in _warn_codes(result)

    def test_does_not_trigger_at_exact_25_pct(self) -> None:
        """Boundary: deposit=50000, price=200000 → exactly 25%, must NOT trigger."""
        result = run_validation(_VALID)
        assert "V-08" not in _warn_codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(
            purchase_price=Decimal("200000"),
            deposit_amount=Decimal("35000"),
        ))
        w = next(w for w in result.warnings if w.rule_code == "V-08")
        assert "25%" in w.message
        assert w.field == "deposit_amount"


# ---------------------------------------------------------------------------
# V-10 — mortgage_interest_rate = 0 (WARN, cash purchase)
# ---------------------------------------------------------------------------

class TestV10ZeroMortgageRate:

    def test_triggers_when_zero(self) -> None:
        result = run_validation(_inp(mortgage_interest_rate=Decimal("0")))
        assert "V-10" in _warn_codes(result)
        assert result.is_valid is True

    def test_does_not_trigger_when_positive(self) -> None:
        result = run_validation(_VALID)
        assert "V-10" not in _warn_codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(mortgage_interest_rate=Decimal("0")))
        w = next(w for w in result.warnings if w.rule_code == "V-10")
        assert "cash purchase" in w.message.lower()


# ---------------------------------------------------------------------------
# V-11 — mortgage_interest_rate > 0 and < 3.0 (WARN, unusually low)
# ---------------------------------------------------------------------------

class TestV11LowMortgageRate:

    def test_triggers_at_2_99(self) -> None:
        result = run_validation(_inp(mortgage_interest_rate=Decimal("2.99")))
        assert "V-11" in _warn_codes(result)

    def test_triggers_at_0_01(self) -> None:
        result = run_validation(_inp(mortgage_interest_rate=Decimal("0.01")))
        assert "V-11" in _warn_codes(result)

    def test_does_not_trigger_at_3_00(self) -> None:
        """Boundary: rate=3.00 must NOT trigger V-11."""
        result = run_validation(_inp(mortgage_interest_rate=Decimal("3.00")))
        assert "V-11" not in _warn_codes(result)

    def test_does_not_trigger_at_zero(self) -> None:
        """Zero triggers V-10, not V-11."""
        result = run_validation(_inp(mortgage_interest_rate=Decimal("0")))
        assert "V-11" not in _warn_codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(mortgage_interest_rate=Decimal("2.99")))
        w = next(w for w in result.warnings if w.rule_code == "V-11")
        assert "unusually low" in w.message.lower()


# ---------------------------------------------------------------------------
# V-12 — mortgage_interest_rate > 10.0 (WARN, unusually high)
# ---------------------------------------------------------------------------

class TestV12HighMortgageRate:

    def test_triggers_at_10_01(self) -> None:
        result = run_validation(_inp(mortgage_interest_rate=Decimal("10.01")))
        assert "V-12" in _warn_codes(result)

    def test_does_not_trigger_at_10_00(self) -> None:
        """Boundary: rate=10.00 must NOT trigger."""
        result = run_validation(_inp(mortgage_interest_rate=Decimal("10.00")))
        assert "V-12" not in _warn_codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(mortgage_interest_rate=Decimal("10.01")))
        w = next(w for w in result.warnings if w.rule_code == "V-12")
        assert "unusually high" in w.message.lower()


# ---------------------------------------------------------------------------
# V-19 — void_rate_percent = 0 (WARN)
# ---------------------------------------------------------------------------

class TestV19ZeroVoidRate:

    def test_triggers_when_zero(self) -> None:
        result = run_validation(_inp(void_rate_percent=Decimal("0")))
        assert "V-19" in _warn_codes(result)
        assert result.is_valid is True

    def test_does_not_trigger_when_positive(self) -> None:
        result = run_validation(_VALID)
        assert "V-19" not in _warn_codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(void_rate_percent=Decimal("0")))
        w = next(w for w in result.warnings if w.rule_code == "V-19")
        assert "vacancy" in w.message.lower()


# ---------------------------------------------------------------------------
# V-20 — letting_agent_fee_percent > 25 (WARN)
# ---------------------------------------------------------------------------

class TestV20HighAgentFee:

    def test_triggers_above_25(self) -> None:
        result = run_validation(_inp(letting_agent_fee_percent=Decimal("25.01")))
        assert "V-20" in _warn_codes(result)

    def test_does_not_trigger_at_25(self) -> None:
        """Boundary: fee=25.00 must NOT trigger."""
        result = run_validation(_inp(letting_agent_fee_percent=Decimal("25.00")))
        assert "V-20" not in _warn_codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(letting_agent_fee_percent=Decimal("25.01")))
        w = next(w for w in result.warnings if w.rule_code == "V-20")
        assert "unusually high" in w.message.lower()


# ---------------------------------------------------------------------------
# V-23 — annual_ground_rent > 250 and LEASEHOLD (WARN)
# ---------------------------------------------------------------------------

class TestV23HighGroundRent:

    def test_triggers_for_leasehold_above_250(self) -> None:
        result = run_validation(_inp(
            tenure=Tenure.LEASEHOLD,
            annual_service_charge=Decimal("1200"),
            annual_ground_rent=Decimal("251"),
        ))
        assert "V-23" in _warn_codes(result)
        assert result.is_valid is True

    def test_does_not_trigger_at_250(self) -> None:
        """Boundary: ground_rent=250 + LEASEHOLD must NOT trigger."""
        result = run_validation(_inp(
            tenure=Tenure.LEASEHOLD,
            annual_service_charge=Decimal("1200"),
            annual_ground_rent=Decimal("250"),
        ))
        assert "V-23" not in _warn_codes(result)

    def test_does_not_trigger_for_freehold_above_250(self) -> None:
        """Tenure must be LEASEHOLD for V-23 to trigger."""
        result = run_validation(_inp(
            tenure=Tenure.FREEHOLD,
            annual_ground_rent=Decimal("251"),
        ))
        assert "V-23" not in _warn_codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(
            tenure=Tenure.LEASEHOLD,
            annual_service_charge=Decimal("1200"),
            annual_ground_rent=Decimal("251"),
        ))
        w = next(w for w in result.warnings if w.rule_code == "V-23")
        assert "£250" in w.message
        assert w.field == "annual_ground_rent"


# ---------------------------------------------------------------------------
# V-24 — maintenance_reserve_percent > 5.0 (WARN)
# ---------------------------------------------------------------------------

class TestV24HighMaintenanceReserve:

    def test_triggers_above_5(self) -> None:
        result = run_validation(_inp(maintenance_reserve_percent=Decimal("5.01")))
        assert "V-24" in _warn_codes(result)

    def test_does_not_trigger_at_5(self) -> None:
        """Boundary: reserve=5.00 must NOT trigger."""
        result = run_validation(_inp(maintenance_reserve_percent=Decimal("5.00")))
        assert "V-24" not in _warn_codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(maintenance_reserve_percent=Decimal("5.01")))
        w = next(w for w in result.warnings if w.rule_code == "V-24")
        assert "unusually high" in w.message.lower()


# ---------------------------------------------------------------------------
# V-25 — refurbishment_cost = 0 (WARN)
# ---------------------------------------------------------------------------

class TestV25ZeroRefurb:

    def test_triggers_when_zero(self) -> None:
        result = run_validation(_inp(refurbishment_cost=Decimal("0")))
        assert "V-25" in _warn_codes(result)
        assert result.is_valid is True

    def test_does_not_trigger_when_positive(self) -> None:
        """_VALID has refurbishment_cost=100, so V-25 should not fire."""
        result = run_validation(_VALID)
        assert "V-25" not in _warn_codes(result)

    def test_does_not_trigger_at_one_penny(self) -> None:
        """Boundary: 0.01 must NOT trigger."""
        result = run_validation(_inp(refurbishment_cost=Decimal("0.01")))
        assert "V-25" not in _warn_codes(result)

    def test_message_matches_spec(self) -> None:
        result = run_validation(_inp(refurbishment_cost=Decimal("0")))
        w = next(w for w in result.warnings if w.rule_code == "V-25")
        assert "refurbishment" in w.message.lower()
        assert w.field == "refurbishment_cost"
