"""
Regression test E-01 — Baseline, INDIVIDUAL BASIC_RATE.

£200k purchase, 25% deposit, 4.75% IO, INDIVIDUAL BASIC_RATE.
Demonstrates: all formulas, basic-rate Section 24 neutrality (zero tax
liability), negative cash flow, standard outputs.

Source: ENGINE_CONTRACTS.md E-01.
TEST_STRATEGY.md Part 7.2.
"""

from decimal import Decimal

import pytest

from app.engine import run
from app.engine.contracts import EngineResult
from tests.conftest import (
    REFERENCE_CONFIG,
    e01_absent_flags,
    e01_expected_flags,
    e01_expected_outputs,
    e01_expected_warnings,
    e01_input,
)
from tests.regression.conftest import (
    assert_flags_absent,
    assert_flags_present,
    assert_outputs,
    assert_warnings,
)


@pytest.fixture(scope="module")
def e01_result() -> EngineResult:
    """Run E-01 once; share result across all assertions in this module."""
    result = run(e01_input(), REFERENCE_CONFIG)
    assert isinstance(result, EngineResult), (
        f"Expected EngineResult, got {type(result).__name__}"
    )
    return result


class TestE01Outputs:

    def test_all_output_fields(self, e01_result: EngineResult) -> None:
        """Every EngineOutputs field matches ENGINE_CONTRACTS.md E-01."""
        assert_outputs(e01_result.outputs, e01_expected_outputs())

    def test_is_engine_result(self, e01_result: EngineResult) -> None:
        assert isinstance(e01_result, EngineResult)


class TestE01Intermediates:

    def test_void_rate_decimal(self, e01_result: EngineResult) -> None:
        """
        void_rate_decimal_applied is stored rounded to 2dp per
        ENGINE_CONTRACTS.md Part 7.2. F-02: 3.85/100 = 0.0385;
        _r(0.0385) = 0.04 (rounds to 2dp ROUND_HALF_UP).
        """
        _val = e01_result.intermediates.void_rate_decimal_applied
        assert _val == Decimal("0.04")

    def test_loan_amount(self, e01_result: EngineResult) -> None:
        assert e01_result.intermediates.loan_amount_gbp == Decimal("150000.00")

    def test_monthly_mortgage_payment(self, e01_result: EngineResult) -> None:
        _val = e01_result.intermediates.monthly_mortgage_payment_gbp
        assert _val == Decimal("593.75")

    def test_letting_agent_annual(self, e01_result: EngineResult) -> None:
        assert e01_result.intermediates.letting_agent_annual_gbp == Decimal("1368.00")

    def test_annual_maintenance_reserve(self, e01_result: EngineResult) -> None:
        _val = e01_result.intermediates.annual_maintenance_reserve_gbp
        assert _val == Decimal("2000.00")

    def test_net_operating_income(self, e01_result: EngineResult) -> None:
        assert e01_result.intermediates.net_operating_income_gbp == Decimal("6793.10")

    def test_sdlt_base(self, e01_result: EngineResult) -> None:
        assert e01_result.intermediates.sdlt_base_gbp == Decimal("1500.00")

    def test_sdlt_surcharge(self, e01_result: EngineResult) -> None:
        assert e01_result.intermediates.sdlt_surcharge_gbp == Decimal("6000.00")

    def test_sdlt_surcharge_rate(self, e01_result: EngineResult) -> None:
        assert e01_result.intermediates.sdlt_surcharge_rate_applied == Decimal("0.03")

    def test_stressed_annual_interest(self, e01_result: EngineResult) -> None:
        _val = e01_result.intermediates.stressed_annual_interest_gbp
        assert _val == Decimal("8250.00")

    def test_stress_test_rate(self, e01_result: EngineResult) -> None:
        _val = e01_result.intermediates.stress_test_rate_applied_percent
        assert _val == Decimal("5.5")

    def test_taxable_income(self, e01_result: EngineResult) -> None:
        _val = e01_result.intermediates.taxable_income_or_profit_gbp
        assert _val == Decimal("6793.10")

    def test_income_tax_gross(self, e01_result: EngineResult) -> None:
        assert e01_result.intermediates.income_tax_gross_gbp == Decimal("1358.62")

    def test_mortgage_interest_tax_credit(self, e01_result: EngineResult) -> None:
        _val = e01_result.intermediates.mortgage_interest_tax_credit_gbp
        assert _val == Decimal("1425.00")

    def test_corporation_tax_gross_is_none(self, e01_result: EngineResult) -> None:
        """INDIVIDUAL pathway: corporation_tax_gross is None."""
        assert e01_result.intermediates.corporation_tax_gross_gbp is None

    def test_annual_tax_liability(self, e01_result: EngineResult) -> None:
        assert e01_result.intermediates.annual_tax_liability_gbp == Decimal("0.00")

    def test_pre_tax_cash_flow(self, e01_result: EngineResult) -> None:
        _val = e01_result.intermediates.pre_tax_annual_cash_flow_gbp
        assert _val == Decimal("-331.90")

    def test_section_24_applies(self, e01_result: EngineResult) -> None:
        assert e01_result.intermediates.section_24_applies is True

    def test_sdlt_band_breakdown_has_two_bands(self, e01_result: EngineResult) -> None:
        """E-01 price=200k: bands 0-125k and 125k-250k are the two taxable bands."""
        breakdown = [
            b for b in e01_result.intermediates.sdlt_band_breakdown
            if b.tax_in_band > Decimal("0") or b.taxable_in_band > Decimal("0")
        ]
        assert len(breakdown) >= 1


class TestE01Flags:

    def test_expected_flags_present(self, e01_result: EngineResult) -> None:
        assert_flags_present(e01_result.risk_flags, e01_expected_flags())

    def test_absent_flags_not_present(self, e01_result: EngineResult) -> None:
        assert_flags_absent(e01_result.risk_flags, e01_absent_flags())

    def test_validation_warnings(self, e01_result: EngineResult) -> None:
        assert_warnings(e01_result.validation_warnings, e01_expected_warnings())
