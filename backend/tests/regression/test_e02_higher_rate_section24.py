"""
Regression test E-02 — HIGHER_RATE taxpayer, Section 24 material impact.

Same inputs as E-01, HIGHER_RATE. Demonstrates Section 24 impact:
tax rate 40% but credit fixed at 20%, creating positive tax liability
and deeper negative cash flow.

Source: ENGINE_CONTRACTS.md E-02.
"""

from decimal import Decimal

import pytest

from app.engine import run
from app.engine.contracts import EngineResult
from tests.conftest import (
    REFERENCE_CONFIG,
    e02_absent_flags,
    e02_expected_flags,
    e02_expected_outputs,
    e02_expected_warnings,
    e02_input,
)
from tests.regression.conftest import (
    assert_flags_absent,
    assert_flags_present,
    assert_outputs,
    assert_warnings,
)


@pytest.fixture(scope="module")
def e02_result() -> EngineResult:
    result = run(e02_input(), REFERENCE_CONFIG)
    assert isinstance(result, EngineResult)
    return result


class TestE02Outputs:

    def test_all_output_fields(self, e02_result: EngineResult) -> None:
        """Every EngineOutputs field matches ENGINE_CONTRACTS.md E-02."""
        assert_outputs(e02_result.outputs, e02_expected_outputs())


class TestE02Intermediates:

    def test_income_tax_gross(self, e02_result: EngineResult) -> None:
        """6,793.10 × 0.40 = 2,717.24"""
        assert e02_result.intermediates.income_tax_gross_gbp == Decimal("2717.24")

    def test_mortgage_interest_tax_credit_unchanged(
        self, e02_result: EngineResult
    ) -> None:
        """Credit is always 20% regardless of marginal rate: 7,125 × 0.20 = 1,425."""
        _val = e02_result.intermediates.mortgage_interest_tax_credit_gbp
        assert _val == Decimal("1425.00")

    def test_annual_tax_liability(self, e02_result: EngineResult) -> None:
        """2,717.24 - 1,425.00 = 1,292.24"""
        assert e02_result.intermediates.annual_tax_liability_gbp == Decimal("1292.24")

    def test_pre_tax_cash_flow_unchanged(self, e02_result: EngineResult) -> None:
        """pre_tax is unchanged from E-01 — tax rate does not affect pre-tax."""
        _val = e02_result.intermediates.pre_tax_annual_cash_flow_gbp
        assert _val == Decimal("-331.90")

    def test_section_24_applies(self, e02_result: EngineResult) -> None:
        assert e02_result.intermediates.section_24_applies is True

    def test_corporation_tax_is_none(self, e02_result: EngineResult) -> None:
        assert e02_result.intermediates.corporation_tax_gross_gbp is None


class TestE02Flags:

    def test_expected_flags_present(self, e02_result: EngineResult) -> None:
        assert_flags_present(e02_result.risk_flags, e02_expected_flags())

    def test_absent_flags_not_present(self, e02_result: EngineResult) -> None:
        assert_flags_absent(e02_result.risk_flags, e02_absent_flags())

    def test_section_24_impact_flag_present(self, e02_result: EngineResult) -> None:
        """SECTION_24_IMPACT fires for HIGHER_RATE INDIVIDUAL."""
        codes = {f.code for f in e02_result.risk_flags}
        assert "SECTION_24_IMPACT" in codes

    def test_low_icr_higher_rate_flag_present(self, e02_result: EngineResult) -> None:
        """LOW_ICR_HIGHER_RATE fires: 132.86 is >= 125 and < 145."""
        codes = {f.code for f in e02_result.risk_flags}
        assert "LOW_ICR_HIGHER_RATE" in codes

    def test_validation_warnings(self, e02_result: EngineResult) -> None:
        assert_warnings(e02_result.validation_warnings, e02_expected_warnings())
