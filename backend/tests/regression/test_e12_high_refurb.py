"""
Regression test E-12 — High refurbishment ratio (> 10% of purchase price).

Same as E-01 but refurbishment_cost=25,000 (12.5% of 200k).
HIGH_REFURB_RATIO fires. total_cash_deployed and total_acquisition change.
V-25 does NOT fire (refurb > 0).

Source: ENGINE_CONTRACTS.md E-12. TEST_STRATEGY.md Part 7.2.
"""

from decimal import Decimal

import pytest

from app.engine import run
from app.engine.contracts import EngineResult
from tests.conftest import (
    REFERENCE_CONFIG,
    e12_absent_flags,
    e12_expected_flags,
    e12_expected_outputs,
    e12_expected_warnings,
    e12_input,
)
from tests.regression.conftest import (
    assert_flags_absent,
    assert_flags_present,
    assert_outputs,
    assert_warnings,
)


@pytest.fixture(scope="module")
def e12_result() -> EngineResult:
    result = run(e12_input(), REFERENCE_CONFIG)
    assert isinstance(result, EngineResult)
    return result


class TestE12HighRefurb:

    def test_all_output_fields(self, e12_result: EngineResult) -> None:
        assert_outputs(e12_result.outputs, e12_expected_outputs())

    def test_total_cash_deployed(self, e12_result: EngineResult) -> None:
        """50,000 + 7,500 + 2,500 + 25,000 = 85,000."""
        assert e12_result.outputs.total_cash_deployed_gbp == Decimal("85000.00")

    def test_total_acquisition_cost(self, e12_result: EngineResult) -> None:
        """200,000 + 7,500 + 2,500 + 25,000 = 235,000."""
        assert e12_result.outputs.total_acquisition_cost_gbp == Decimal("235000.00")

    def test_high_refurb_ratio_fires(self, e12_result: EngineResult) -> None:
        """25,000 > 200,000 × 0.10 = 20,000 → HIGH_REFURB_RATIO fires."""
        codes = {f.code for f in e12_result.risk_flags}
        assert "HIGH_REFURB_RATIO" in codes

    def test_high_refurb_triggered_by_value(self, e12_result: EngineResult) -> None:
        flag = next(
            f for f in e12_result.risk_flags if f.code == "HIGH_REFURB_RATIO"
        )
        assert flag.triggered_by_field == "refurbishment_cost"
        assert flag.triggered_by_value == "25000.00"

    def test_v25_not_in_warnings(self, e12_result: EngineResult) -> None:
        """refurb=25,000 — V-25 does NOT fire (refurb > 0)."""
        warn_codes = {w.rule_code for w in e12_result.validation_warnings}
        assert "V-25" not in warn_codes

    def test_expected_flags_present(self, e12_result: EngineResult) -> None:
        assert_flags_present(e12_result.risk_flags, e12_expected_flags())

    def test_absent_flags_not_present(self, e12_result: EngineResult) -> None:
        assert_flags_absent(e12_result.risk_flags, e12_absent_flags())

    def test_validation_warnings(self, e12_result: EngineResult) -> None:
        assert_warnings(e12_result.validation_warnings, e12_expected_warnings())
