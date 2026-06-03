"""
Regression test E-10 — ADDITIONAL_RATE, maximum Section 24 impact.

Same as E-01 but ADDITIONAL_RATE. tax rate=45%, credit fixed at 20%.
Maximum divergence between rate and credit.

Source: ENGINE_CONTRACTS.md E-10. TEST_STRATEGY.md Part 7.2.
"""

from decimal import Decimal

import pytest

from app.engine import run
from app.engine.contracts import EngineResult
from tests.conftest import (
    REFERENCE_CONFIG,
    e10_expected_flags,
    e10_expected_outputs,
    e10_expected_warnings,
    e10_input,
)
from tests.regression.conftest import (
    assert_flags_present,
    assert_outputs,
    assert_warnings,
)


@pytest.fixture(scope="module")
def e10_result() -> EngineResult:
    result = run(e10_input(), REFERENCE_CONFIG)
    assert isinstance(result, EngineResult)
    return result


class TestE10AdditionalRate:

    def test_all_output_fields(self, e10_result: EngineResult) -> None:
        """Outputs that change from E-01 and unchanged outputs both correct."""
        assert_outputs(e10_result.outputs, e10_expected_outputs())

    def test_income_tax_gross(self, e10_result: EngineResult) -> None:
        """6,793.10 × 0.45 = 3,056.90"""
        _val = e10_result.intermediates.income_tax_gross_gbp
        assert _val == Decimal("3056.90")

    def test_mortgage_credit_unchanged(self, e10_result: EngineResult) -> None:
        """Credit is always 20% regardless of marginal rate: 7,125 × 0.20 = 1,425."""
        _val = e10_result.intermediates.mortgage_interest_tax_credit_gbp
        assert _val == Decimal("1425.00")

    def test_annual_tax_liability(self, e10_result: EngineResult) -> None:
        """3,056.90 - 1,425.00 = 1,631.90"""
        _val = e10_result.intermediates.annual_tax_liability_gbp
        assert _val == Decimal("1631.90")

    def test_section_24_applies(self, e10_result: EngineResult) -> None:
        assert e10_result.intermediates.section_24_applies is True

    def test_expected_flags_present(self, e10_result: EngineResult) -> None:
        assert_flags_present(e10_result.risk_flags, e10_expected_flags())

    def test_section_24_impact_fires(self, e10_result: EngineResult) -> None:
        codes = {f.code for f in e10_result.risk_flags}
        assert "SECTION_24_IMPACT" in codes

    def test_low_icr_higher_rate_fires(self, e10_result: EngineResult) -> None:
        """132.86 is >= 125 and < 145, ADDITIONAL_RATE → LOW_ICR_HIGHER_RATE fires."""
        codes = {f.code for f in e10_result.risk_flags}
        assert "LOW_ICR_HIGHER_RATE" in codes

    def test_validation_warnings(self, e10_result: EngineResult) -> None:
        assert_warnings(e10_result.validation_warnings, e10_expected_warnings())
