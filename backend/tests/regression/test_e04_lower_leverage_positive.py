"""
Regression test E-04 — Lower leverage (60% LTV), positive cash flow.

Same as E-01 but deposit=80,000 (40%). Demonstrates: lower mortgage cost
produces positive cash flow and clears most HIGH flags. Conservative
investor baseline.

Source: ENGINE_CONTRACTS.md E-04.
"""

from decimal import Decimal

import pytest

from app.engine import run
from app.engine.contracts import EngineResult
from tests.conftest import (
    REFERENCE_CONFIG,
    e04_absent_flags,
    e04_expected_flags,
    e04_expected_outputs,
    e04_expected_warnings,
    e04_input,
)
from tests.regression.conftest import (
    assert_flags_absent,
    assert_flags_present,
    assert_outputs,
    assert_warnings,
)


@pytest.fixture(scope="module")
def e04_result() -> EngineResult:
    result = run(e04_input(), REFERENCE_CONFIG)
    assert isinstance(result, EngineResult)
    return result


class TestE04Outputs:

    def test_all_output_fields(self, e04_result: EngineResult) -> None:
        """Every EngineOutputs field matches ENGINE_CONTRACTS.md E-04."""
        assert_outputs(e04_result.outputs, e04_expected_outputs())

    def test_positive_cash_flow(self, e04_result: EngineResult) -> None:
        """Lower leverage produces positive cash flow."""
        assert e04_result.outputs.annual_cash_flow_gbp > Decimal("0")

    def test_ltv_is_60(self, e04_result: EngineResult) -> None:
        assert e04_result.outputs.ltv_percent == Decimal("60.00")


class TestE04Intermediates:

    def test_loan_amount(self, e04_result: EngineResult) -> None:
        """200,000 - 80,000 = 120,000"""
        assert e04_result.intermediates.loan_amount_gbp == Decimal("120000.00")

    def test_annual_mortgage_cost(self, e04_result: EngineResult) -> None:
        """120,000 × 4.75% = 5,700.00"""
        assert e04_result.intermediates.annual_mortgage_cost_gbp == Decimal("5700.00")

    def test_stressed_annual_interest(self, e04_result: EngineResult) -> None:
        """120,000 × 5.5% = 6,600.00"""
        _val = e04_result.intermediates.stressed_annual_interest_gbp
        assert _val == Decimal("6600.00")

    def test_tax_credit(self, e04_result: EngineResult) -> None:
        """5,700 × 20% = 1,140.00"""
        _val = e04_result.intermediates.mortgage_interest_tax_credit_gbp
        assert _val == Decimal("1140.00")

    def test_annual_tax_liability(self, e04_result: EngineResult) -> None:
        """1,358.62 - 1,140.00 = 218.62"""
        assert e04_result.intermediates.annual_tax_liability_gbp == Decimal("218.62")

    def test_pre_tax_cash_flow(self, e04_result: EngineResult) -> None:
        """noi=6,793.10 - mortgage=5,700 = 1,093.10"""
        _val = e04_result.intermediates.pre_tax_annual_cash_flow_gbp
        assert _val == Decimal("1093.10")

    def test_total_cash_deployed(self, e04_result: EngineResult) -> None:
        """80,000 + 7,500 + 2,500 + 0 = 90,000"""
        assert e04_result.intermediates.total_cash_deployed_gbp == Decimal("90000.00")

    def test_section_24_applies(self, e04_result: EngineResult) -> None:
        assert e04_result.intermediates.section_24_applies is True


class TestE04Flags:

    def test_expected_flags_present(self, e04_result: EngineResult) -> None:
        assert_flags_present(e04_result.risk_flags, e04_expected_flags())

    def test_absent_flags_not_present(self, e04_result: EngineResult) -> None:
        assert_flags_absent(e04_result.risk_flags, e04_absent_flags())

    def test_negative_cashflow_not_present(self, e04_result: EngineResult) -> None:
        codes = {f.code for f in e04_result.risk_flags}
        assert "NEGATIVE_CASHFLOW" not in codes

    def test_high_leverage_not_present(self, e04_result: EngineResult) -> None:
        """60% LTV is below the 75% threshold."""
        codes = {f.code for f in e04_result.risk_flags}
        assert "HIGH_LEVERAGE" not in codes

    def test_validation_warnings(self, e04_result: EngineResult) -> None:
        assert_warnings(e04_result.validation_warnings, e04_expected_warnings())
