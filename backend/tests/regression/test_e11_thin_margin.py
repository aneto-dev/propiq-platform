"""
Regression test E-11 — Thin margin safety (positive but < 5% of gross rent).

£220k, 3.80% IO. cash_flow=258.48, gross_rent=11,400.
258.48 / 11,400 = 2.27% < 5% → LOW_MARGIN_SAFETY fires.

Source: ENGINE_CONTRACTS.md E-11. TEST_STRATEGY.md Part 7.2.
"""

from decimal import Decimal

import pytest

from app.engine import run
from app.engine.contracts import EngineResult
from tests.conftest import (
    REFERENCE_CONFIG,
    e11_absent_flags,
    e11_expected_flags,
    e11_expected_outputs,
    e11_expected_warnings,
    e11_input,
)
from tests.regression.conftest import (
    assert_flags_absent,
    assert_flags_present,
    assert_outputs,
    assert_warnings,
)


@pytest.fixture(scope="module")
def e11_result() -> EngineResult:
    result = run(e11_input(), REFERENCE_CONFIG)
    assert isinstance(result, EngineResult)
    return result


class TestE11ThinMargin:

    def test_all_output_fields(self, e11_result: EngineResult) -> None:
        assert_outputs(e11_result.outputs, e11_expected_outputs())

    def test_cash_flow_positive(self, e11_result: EngineResult) -> None:
        """Cash flow is positive (258.48) but margin < 5%."""
        assert e11_result.outputs.annual_cash_flow_gbp > Decimal("0")

    def test_low_margin_safety_fires(self, e11_result: EngineResult) -> None:
        """258.48 / 11,400 = 2.27% < 5% → LOW_MARGIN_SAFETY fires."""
        codes = {f.code for f in e11_result.risk_flags}
        assert "LOW_MARGIN_SAFETY" in codes

    def test_negative_cashflow_absent(self, e11_result: EngineResult) -> None:
        """Cash flow is positive — NEGATIVE_CASHFLOW must not fire."""
        codes = {f.code for f in e11_result.risk_flags}
        assert "NEGATIVE_CASHFLOW" not in codes

    def test_low_margin_triggered_by_value(self, e11_result: EngineResult) -> None:
        flag = next(
            f for f in e11_result.risk_flags if f.code == "LOW_MARGIN_SAFETY"
        )
        assert flag.triggered_by_field == "annual_cash_flow_gbp"
        assert flag.triggered_by_value == "258.48"

    def test_expected_flags_present(self, e11_result: EngineResult) -> None:
        assert_flags_present(e11_result.risk_flags, e11_expected_flags())

    def test_absent_flags_not_present(self, e11_result: EngineResult) -> None:
        assert_flags_absent(e11_result.risk_flags, e11_absent_flags())

    def test_validation_warnings(self, e11_result: EngineResult) -> None:
        assert_warnings(e11_result.validation_warnings, e11_expected_warnings())
