"""
Pipeline-level validation tests.

Tests the validation pipeline as a whole system: multiple simultaneous
failures, HARD+WARN combinations, is_valid flag, result structure.

Source: TEST_STRATEGY.md Part 5.5.
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
from app.engine.contracts import EngineInput, ValidationError, ValidationWarning
from app.engine.validation.rules import VALIDATION_RULES, run_validation

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


class TestValidationPipelineMultipleErrors:

    def test_collects_all_hard_errors_not_just_first(self) -> None:
        """
        Pipeline must collect ALL failures, not stop at first error.
        V-01 (price=0) AND V-04 (rent=0) must both appear in hard_errors.
        Source: TEST_STRATEGY.md Part 5.5.
        """
        result = run_validation(_inp(
            purchase_price=Decimal("0"),
            monthly_rent=Decimal("0"),
        ))
        codes = {e.rule_code for e in result.hard_errors}
        assert "V-01" in codes
        assert "V-04" in codes
        assert result.is_valid is False

    def test_hard_and_warn_simultaneously(self) -> None:
        """
        V-07 HARD (deposit too low) and V-25 WARN (refurb=0) trigger together.
        hard_errors contains V-07; warnings contains V-25; is_valid=False.
        Source: TEST_STRATEGY.md Part 5.5.
        """
        result = run_validation(_inp(
            deposit_amount=Decimal("25000"),
            refurbishment_cost=Decimal("0"),
        ))
        hard_codes = {e.rule_code for e in result.hard_errors}
        warn_codes = {w.rule_code for w in result.warnings}
        assert "V-07" in hard_codes
        assert "V-25" in warn_codes
        assert result.is_valid is False

    def test_warn_only_is_valid_true(self) -> None:
        """
        Only V-25 (WARN) triggered. is_valid must be True.
        Source: TEST_STRATEGY.md Part 5.5.
        """
        result = run_validation(_inp(refurbishment_cost=Decimal("0")))
        assert result.is_valid is True
        assert len(result.hard_errors) == 0
        assert any(w.rule_code == "V-25" for w in result.warnings)

    def test_clean_input_produces_empty_results(self) -> None:
        """_VALID has refurb=100, void=3.85, deposit=50k — no rules trigger."""
        result = run_validation(_VALID)
        assert result.is_valid is True
        assert len(result.hard_errors) == 0
        assert len(result.warnings) == 0


class TestValidationCrossFieldRules:

    def test_v17_does_not_trigger_for_ltd_co_null_band(self) -> None:
        """
        LIMITED_COMPANY + income_tax_band=None must NOT trigger V-17.
        V-17 applies only to INDIVIDUAL.
        Source: TEST_STRATEGY.md Part 5.5.
        """
        result = run_validation(_inp(
            ownership_structure=OwnershipStructure.LIMITED_COMPANY,
            income_tax_band=None,
        ))
        codes = {e.rule_code for e in result.hard_errors}
        assert "V-17" not in codes

    def test_v21_v22_do_not_trigger_for_freehold_null(self) -> None:
        """
        FREEHOLD + annual_service_charge=None + annual_ground_rent=None.
        V-21 and V-22 must NOT trigger (they apply only to LEASEHOLD).
        Source: TEST_STRATEGY.md Part 5.5.
        """
        result = run_validation(_inp(
            tenure=Tenure.FREEHOLD,
            annual_service_charge=Decimal("0"),
            annual_ground_rent=Decimal("0"),
        ))
        codes = {e.rule_code for e in result.hard_errors}
        assert "V-21" not in codes
        assert "V-22" not in codes


class TestValidationResultStructure:

    def test_every_hard_error_has_required_fields(self) -> None:
        """
        Every ValidationError must have: rule_code, field, message — all
        non-empty strings matching CALCULATION_SPEC.md.
        Source: TEST_STRATEGY.md Part 5.5.
        """
        result = run_validation(_inp(purchase_price=Decimal("0")))
        for err in result.hard_errors:
            assert isinstance(err, ValidationError)
            assert isinstance(err.rule_code, str) and err.rule_code
            assert isinstance(err.field, str) and err.field
            assert isinstance(err.message, str) and err.message

    def test_every_warning_has_required_fields(self) -> None:
        """Every ValidationWarning must have non-empty rule_code, field, message."""
        result = run_validation(_inp(refurbishment_cost=Decimal("0")))
        for w in result.warnings:
            assert isinstance(w, ValidationWarning)
            assert isinstance(w.rule_code, str) and w.rule_code
            assert isinstance(w.field, str) and w.field
            assert isinstance(w.message, str) and w.message

    def test_hard_errors_and_warnings_are_separate_lists(self) -> None:
        """
        hard_errors and warnings must be separate lists.
        No code must appear in both simultaneously.
        """
        result = run_validation(_inp(
            deposit_amount=Decimal("25000"),
            refurbishment_cost=Decimal("0"),
        ))
        hard_codes = {e.rule_code for e in result.hard_errors}
        warn_codes = {w.rule_code for w in result.warnings}
        assert hard_codes.isdisjoint(warn_codes), (
            f"Same code in both lists: {hard_codes & warn_codes}"
        )

    def test_25_rules_defined(self) -> None:
        """VALIDATION_RULES must contain exactly 25 rules."""
        assert len(VALIDATION_RULES) == 25

    def test_rule_codes_are_unique(self) -> None:
        """Every rule code must be unique in VALIDATION_RULES."""
        codes = [r.code for r in VALIDATION_RULES]
        assert len(codes) == len(set(codes))
