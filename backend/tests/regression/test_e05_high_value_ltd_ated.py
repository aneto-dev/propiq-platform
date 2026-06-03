"""
Regression test E-05 — High-value Ltd Co purchase, ATED + LOW_ICR_BASIC.

£600k, LIMITED_COMPANY, 5.25% IO. Demonstrates: ATED threshold crossed
(> £500k), LOW_ICR_BASIC fires (111.88 < 125), negative cash flow on a
high-value deal.

Source: ENGINE_CONTRACTS.md E-05.
"""

from decimal import Decimal

import pytest

from app.engine import run
from app.engine.contracts import EngineResult
from tests.conftest import (
    REFERENCE_CONFIG,
    e05_absent_flags,
    e05_expected_flags,
    e05_expected_outputs,
    e05_expected_warnings,
    e05_input,
)
from tests.regression.conftest import (
    assert_flags_absent,
    assert_flags_present,
    assert_outputs,
    assert_warnings,
)


@pytest.fixture(scope="module")
def e05_result() -> EngineResult:
    result = run(e05_input(), REFERENCE_CONFIG)
    assert isinstance(result, EngineResult)
    return result


class TestE05Outputs:

    def test_all_output_fields(self, e05_result: EngineResult) -> None:
        """Every EngineOutputs field matches ENGINE_CONTRACTS.md E-05."""
        assert_outputs(e05_result.outputs, e05_expected_outputs())


class TestE05Intermediates:

    def test_taxable_profit_negative(self, e05_result: EngineResult) -> None:
        _val = e05_result.intermediates.taxable_income_or_profit_gbp
        assert _val == Decimal("-7389.80")

    def test_corporation_tax_zero(self, e05_result: EngineResult) -> None:
        assert e05_result.intermediates.corporation_tax_gross_gbp == Decimal("0.00")

    def test_section_24_applies_false(self, e05_result: EngineResult) -> None:
        assert e05_result.intermediates.section_24_applies is False

    def test_stressed_annual_interest(self, e05_result: EngineResult) -> None:
        """450,000 × 5.5% = 24,750.00"""
        _val = e05_result.intermediates.stressed_annual_interest_gbp
        assert _val == Decimal("24750.00")

    def test_total_sdlt(self, e05_result: EngineResult) -> None:
        """sdlt_base=20,000 + surcharge=18,000 = 38,000."""
        assert e05_result.intermediates.total_sdlt_gbp == Decimal("38000.00")

    def test_income_tax_fields_none(self, e05_result: EngineResult) -> None:
        assert e05_result.intermediates.income_tax_gross_gbp is None
        assert e05_result.intermediates.mortgage_interest_tax_credit_gbp is None


class TestE05Flags:

    def test_expected_flags_present(self, e05_result: EngineResult) -> None:
        assert_flags_present(e05_result.risk_flags, e05_expected_flags())

    def test_absent_flags_not_present(self, e05_result: EngineResult) -> None:
        assert_flags_absent(e05_result.risk_flags, e05_absent_flags())

    def test_ated_warning_present(self, e05_result: EngineResult) -> None:
        codes = {f.code for f in e05_result.risk_flags}
        assert "ATED_WARNING" in codes

    def test_low_icr_basic_present(self, e05_result: EngineResult) -> None:
        """icr=111.88 < 125 → LOW_ICR_BASIC fires."""
        codes = {f.code for f in e05_result.risk_flags}
        assert "LOW_ICR_BASIC" in codes

    def test_validation_warnings(self, e05_result: EngineResult) -> None:
        assert_warnings(e05_result.validation_warnings, e05_expected_warnings())
