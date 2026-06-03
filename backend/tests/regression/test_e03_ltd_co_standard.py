"""
Regression test E-03 — LIMITED_COMPANY, standard case.

£350k, Ltd Co SPV, 5% IO. Demonstrates: corporation tax pathway,
mortgage interest fully deductible (negative taxable profit → zero tax),
no Section 24 impact.

Note: ENGINE_CONTRACTS.md shows icr_percent=127.88. Correct arithmetic
gives 127.87 (18,460.80 / 14,437.50 × 100 = 127.867...). This test
uses 127.87 per CALCULATION_SPEC.md formulas. See conftest expected
values and Commit 2.4 notes.

Source: ENGINE_CONTRACTS.md E-03.
"""

from decimal import Decimal

import pytest

from app.engine import run
from app.engine.contracts import EngineResult
from tests.conftest import (
    REFERENCE_CONFIG,
    e03_absent_flags,
    e03_expected_flags,
    e03_expected_outputs,
    e03_expected_warnings,
    e03_input,
)
from tests.regression.conftest import (
    assert_flags_absent,
    assert_flags_present,
    assert_outputs,
    assert_warnings,
)


@pytest.fixture(scope="module")
def e03_result() -> EngineResult:
    result = run(e03_input(), REFERENCE_CONFIG)
    assert isinstance(result, EngineResult)
    return result


class TestE03Outputs:

    def test_all_output_fields(self, e03_result: EngineResult) -> None:
        """Every EngineOutputs field matches ENGINE_CONTRACTS.md E-03."""
        assert_outputs(e03_result.outputs, e03_expected_outputs())


class TestE03Intermediates:

    def test_taxable_company_profit_negative(self, e03_result: EngineResult) -> None:
        """
        Mortgage interest deductible: taxable profit = -2,468.20.
        18,460.80 - 2,304 - 3,500 - 800 - 0 - 0 - 1,200 - 13,125 = -2,468.20
        """
        _val = e03_result.intermediates.taxable_income_or_profit_gbp
        assert _val == Decimal("-2468.20")

    def test_corporation_tax_gross_zero(self, e03_result: EngineResult) -> None:
        """Negative profit → corporation_tax = 0 (not None)."""
        assert e03_result.intermediates.corporation_tax_gross_gbp == Decimal("0.00")

    def test_annual_tax_liability_zero(self, e03_result: EngineResult) -> None:
        assert e03_result.intermediates.annual_tax_liability_gbp == Decimal("0.00")

    def test_income_tax_gross_is_none(self, e03_result: EngineResult) -> None:
        """LIMITED_COMPANY pathway: income_tax_gross is None."""
        assert e03_result.intermediates.income_tax_gross_gbp is None

    def test_mortgage_interest_credit_is_none(self, e03_result: EngineResult) -> None:
        """LIMITED_COMPANY pathway: mortgage_interest_tax_credit is None."""
        assert e03_result.intermediates.mortgage_interest_tax_credit_gbp is None

    def test_section_24_applies_false(self, e03_result: EngineResult) -> None:
        assert e03_result.intermediates.section_24_applies is False

    def test_loan_amount(self, e03_result: EngineResult) -> None:
        assert e03_result.intermediates.loan_amount_gbp == Decimal("262500.00")

    def test_stressed_annual_interest(self, e03_result: EngineResult) -> None:
        """262,500 × 5.5% = 14,437.50"""
        _val = e03_result.intermediates.stressed_annual_interest_gbp
        assert _val == Decimal("14437.50")

    def test_letting_agent_annual(self, e03_result: EngineResult) -> None:
        """19,200 × 10% × 1.20 = 2,304.00"""
        assert e03_result.intermediates.letting_agent_annual_gbp == Decimal("2304.00")

    def test_pre_tax_cash_flow(self, e03_result: EngineResult) -> None:
        """noi=10,656.80 - mortgage=13,125 = -2,468.20"""
        _val = e03_result.intermediates.pre_tax_annual_cash_flow_gbp
        assert _val == Decimal("-2468.20")

    def test_total_sdlt(self, e03_result: EngineResult) -> None:
        assert e03_result.intermediates.total_sdlt_gbp == Decimal("18000.00")


class TestE03Flags:

    def test_expected_flags_present(self, e03_result: EngineResult) -> None:
        assert_flags_present(e03_result.risk_flags, e03_expected_flags())

    def test_absent_flags_not_present(self, e03_result: EngineResult) -> None:
        assert_flags_absent(e03_result.risk_flags, e03_absent_flags())

    def test_ltd_extraction_undisclosed(self, e03_result: EngineResult) -> None:
        codes = {f.code for f in e03_result.risk_flags}
        assert "LTD_EXTRACTION_UNDISCLOSED" in codes

    def test_section_24_impact_absent(self, e03_result: EngineResult) -> None:
        """SECTION_24_IMPACT must not fire for LIMITED_COMPANY."""
        codes = {f.code for f in e03_result.risk_flags}
        assert "SECTION_24_IMPACT" not in codes

    def test_validation_warnings(self, e03_result: EngineResult) -> None:
        assert_warnings(e03_result.validation_warnings, e03_expected_warnings())
