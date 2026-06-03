"""
Regression test E-06 — Leasehold flat, HIGHER_RATE, service charge, ground rent.

£180k leasehold, 95-year lease, HIGHER_RATE individual. Demonstrates:
service charge and ground rent in operating costs, Section 24 material
impact at HIGHER_RATE, LEASEHOLD_SHORT_LEASE does NOT fire (lease=95 > 80).

Source: ENGINE_CONTRACTS.md E-06.
"""

from decimal import Decimal

import pytest

from app.engine import run
from app.engine.contracts import EngineResult
from tests.conftest import (
    REFERENCE_CONFIG,
    e06_absent_flags,
    e06_expected_flags,
    e06_expected_outputs,
    e06_expected_warnings,
    e06_input,
)
from tests.regression.conftest import (
    assert_flags_absent,
    assert_flags_present,
    assert_outputs,
    assert_warnings,
)


@pytest.fixture(scope="module")
def e06_result() -> EngineResult:
    result = run(e06_input(), REFERENCE_CONFIG)
    assert isinstance(result, EngineResult)
    return result


class TestE06Outputs:

    def test_all_output_fields(self, e06_result: EngineResult) -> None:
        """Every EngineOutputs field matches ENGINE_CONTRACTS.md E-06."""
        assert_outputs(e06_result.outputs, e06_expected_outputs())


class TestE06Intermediates:

    def test_total_operating_costs(self, e06_result: EngineResult) -> None:
        """
        1,224 (letting) + 1,800 (maintenance) + 800 (insurance)
        + 1,200 (service charge) + 150 (ground rent) + 0 (accountancy) = 5,174.
        """
        _val = e06_result.intermediates.total_operating_costs_annual_gbp
        assert _val == Decimal("5174.00")

    def test_taxable_rental_income(self, e06_result: EngineResult) -> None:
        """9,807.30 - 5,174 = 4,633.30"""
        _val = e06_result.intermediates.taxable_income_or_profit_gbp
        assert _val == Decimal("4633.30")

    def test_income_tax_gross(self, e06_result: EngineResult) -> None:
        """4,633.30 × 0.40 = 1,853.32"""
        assert e06_result.intermediates.income_tax_gross_gbp == Decimal("1853.32")

    def test_mortgage_interest_tax_credit(self, e06_result: EngineResult) -> None:
        """6,412.50 × 0.20 = 1,282.50"""
        _val = e06_result.intermediates.mortgage_interest_tax_credit_gbp
        assert _val == Decimal("1282.50")

    def test_annual_tax_liability(self, e06_result: EngineResult) -> None:
        """1,853.32 - 1,282.50 = 570.82"""
        assert e06_result.intermediates.annual_tax_liability_gbp == Decimal("570.82")

    def test_section_24_applies(self, e06_result: EngineResult) -> None:
        assert e06_result.intermediates.section_24_applies is True

    def test_pre_tax_cash_flow(self, e06_result: EngineResult) -> None:
        """noi=4,633.30 - mortgage=6,412.50 = -1,779.20"""
        _val = e06_result.intermediates.pre_tax_annual_cash_flow_gbp
        assert _val == Decimal("-1779.20")

    def test_loan_amount(self, e06_result: EngineResult) -> None:
        assert e06_result.intermediates.loan_amount_gbp == Decimal("135000.00")

    def test_stressed_annual_interest(self, e06_result: EngineResult) -> None:
        """135,000 × 5.5% = 7,425.00"""
        _val = e06_result.intermediates.stressed_annual_interest_gbp
        assert _val == Decimal("7425.00")


class TestE06Flags:

    def test_expected_flags_present(self, e06_result: EngineResult) -> None:
        assert_flags_present(e06_result.risk_flags, e06_expected_flags())

    def test_absent_flags_not_present(self, e06_result: EngineResult) -> None:
        assert_flags_absent(e06_result.risk_flags, e06_absent_flags())

    def test_leasehold_short_lease_absent(self, e06_result: EngineResult) -> None:
        """Lease=95 years — LEASEHOLD_SHORT_LEASE must NOT fire."""
        codes = {f.code for f in e06_result.risk_flags}
        assert "LEASEHOLD_SHORT_LEASE" not in codes

    def test_section_24_impact_present(self, e06_result: EngineResult) -> None:
        codes = {f.code for f in e06_result.risk_flags}
        assert "SECTION_24_IMPACT" in codes

    def test_validation_warnings(self, e06_result: EngineResult) -> None:
        assert_warnings(e06_result.validation_warnings, e06_expected_warnings())
