"""
Regression test E-09 — Leasehold short lease flag.

Same as E-06 but lease_years_remaining=72 (below 80-year threshold).
LEASEHOLD_SHORT_LEASE fires. All other outputs identical to E-06.

Source: ENGINE_CONTRACTS.md E-09. TEST_STRATEGY.md Part 7.2.
"""

from decimal import Decimal

import pytest

from app.engine import run
from app.engine.contracts import EngineResult
from tests.conftest import (
    REFERENCE_CONFIG,
    e09_expected_flags,
    e09_input,
)
from tests.regression.conftest import assert_flags_present


@pytest.fixture(scope="module")
def e09_result() -> EngineResult:
    result = run(e09_input(), REFERENCE_CONFIG)
    assert isinstance(result, EngineResult)
    return result


class TestE09ShortLeaseFlag:

    def test_returns_engine_result(self, e09_result: EngineResult) -> None:
        assert isinstance(e09_result, EngineResult)

    def test_leasehold_short_lease_fires(self, e09_result: EngineResult) -> None:
        """lease_years=72 < 80 → LEASEHOLD_SHORT_LEASE fires."""
        codes = {f.code for f in e09_result.risk_flags}
        assert "LEASEHOLD_SHORT_LEASE" in codes

    def test_leasehold_short_lease_triggered_by_value(
        self, e09_result: EngineResult
    ) -> None:
        """triggered_by_value must be "72" — the exact lease years."""
        flag = next(
            f for f in e09_result.risk_flags
            if f.code == "LEASEHOLD_SHORT_LEASE"
        )
        assert flag.triggered_by_value == "72"
        assert flag.triggered_by_field == "lease_years_remaining"

    def test_all_e09_flags_present(self, e09_result: EngineResult) -> None:
        """E-09 = E-06 flags plus LEASEHOLD_SHORT_LEASE."""
        assert_flags_present(e09_result.risk_flags, e09_expected_flags())

    def test_outputs_identical_to_e06(self, e09_result: EngineResult) -> None:
        """lease_years_remaining does not affect any calculated output."""
        assert e09_result.outputs.net_operating_income_gbp == Decimal("4633.30")
        assert e09_result.outputs.annual_cash_flow_gbp == Decimal("-2350.02")
        assert e09_result.outputs.icr_percent == Decimal("132.08")
