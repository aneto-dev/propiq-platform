"""
Regression test E-08 — WARN-only validation, deposit below 25%.

deposit_amount=35,000 (17.5% of 200k). Above 15% (V-07 does not fire),
below 25% (V-08 fires as WARN). Calculation proceeds.
V-25 also fires (refurb=0). HIGH_LEVERAGE fires (ltv=82.5 > 75).

Source: ENGINE_CONTRACTS.md E-08. TEST_STRATEGY.md Part 7.2.
"""

from decimal import Decimal

import pytest

from app.engine import run
from app.engine.contracts import EngineResult
from tests.conftest import (
    REFERENCE_CONFIG,
    e08_absent_flags,
    e08_expected_flags,
    e08_expected_warnings,
    e08_input,
)
from tests.regression.conftest import (
    assert_flags_absent,
    assert_flags_present,
    assert_warnings,
)


@pytest.fixture(scope="module")
def e08_result() -> EngineResult:
    result = run(e08_input(), REFERENCE_CONFIG)
    assert isinstance(result, EngineResult)
    return result


class TestE08WarnOnlyValidation:

    def test_returns_engine_result(self, e08_result: EngineResult) -> None:
        """WARN-only → calculation proceeds → EngineResult returned."""
        assert isinstance(e08_result, EngineResult)

    def test_v08_in_validation_warnings(self, e08_result: EngineResult) -> None:
        """V-08 carried forward into EngineResult.validation_warnings."""
        warn_codes = {w.rule_code for w in e08_result.validation_warnings}
        assert "V-08" in warn_codes

    def test_v25_in_validation_warnings(self, e08_result: EngineResult) -> None:
        warn_codes = {w.rule_code for w in e08_result.validation_warnings}
        assert "V-25" in warn_codes

    def test_no_hard_errors(self, e08_result: EngineResult) -> None:
        assert e08_result.validation_warnings is not None
        # All warnings, no hard failures
        assert len(e08_result.validation_warnings) >= 1

    def test_ltv_is_82_50(self, e08_result: EngineResult) -> None:
        """deposit=35k, price=200k → loan=165k → ltv=82.50%"""
        assert e08_result.outputs.ltv_percent == Decimal("82.50")

    def test_high_leverage_present(self, e08_result: EngineResult) -> None:
        """82.50 > 75 → HIGH_LEVERAGE fires."""
        codes = {f.code for f in e08_result.risk_flags}
        assert "HIGH_LEVERAGE" in codes

    def test_high_leverage_extreme_absent(self, e08_result: EngineResult) -> None:
        """82.50 is not > 85 → HIGH_LEVERAGE_EXTREME does NOT fire."""
        codes = {f.code for f in e08_result.risk_flags}
        assert "HIGH_LEVERAGE_EXTREME" not in codes

    def test_expected_flags_present(self, e08_result: EngineResult) -> None:
        assert_flags_present(e08_result.risk_flags, e08_expected_flags())

    def test_absent_flags_not_present(self, e08_result: EngineResult) -> None:
        assert_flags_absent(e08_result.risk_flags, e08_absent_flags())

    def test_validation_warnings(self, e08_result: EngineResult) -> None:
        assert_warnings(e08_result.validation_warnings, e08_expected_warnings())
