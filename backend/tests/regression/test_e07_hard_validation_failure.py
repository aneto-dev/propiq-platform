"""
Regression test E-07 — HARD validation failure (V-07: deposit below 15%).

deposit_amount=25,000 is 12.5% of 200,000.
V-07 fires: deposit < purchase_price × 0.15.
ValidationResult returned — EngineResult never produced.

Source: ENGINE_CONTRACTS.md E-07. TEST_STRATEGY.md Part 7.4.
"""


import pytest

from app.engine import run
from app.engine.contracts import EngineResult, ValidationResult
from tests.conftest import (
    REFERENCE_CONFIG,
    e07_expected_hard_error_code,
    e07_expected_warnings,
    e07_input,
)


class TestE07HardValidationFailure:

    @pytest.fixture(scope="class")
    def e07_result(self):
        return run(e07_input(), REFERENCE_CONFIG)

    def test_returns_validation_result(self, e07_result) -> None:
        """Return type must be ValidationResult, not EngineResult."""
        assert isinstance(e07_result, ValidationResult)

    def test_is_valid_false(self, e07_result) -> None:
        assert e07_result.is_valid is False

    def test_hard_error_code_is_v07(self, e07_result) -> None:
        codes = {e.rule_code for e in e07_result.hard_errors}
        assert e07_expected_hard_error_code() in codes

    def test_hard_error_field_is_deposit(self, e07_result) -> None:
        err = next(e for e in e07_result.hard_errors if e.rule_code == "V-07")
        assert err.field == "deposit_amount"

    def test_not_engine_result(self, e07_result) -> None:
        """No EngineResult sub-structure exists — engine never ran."""
        assert not isinstance(e07_result, EngineResult)

    def test_no_engine_outputs(self, e07_result) -> None:
        assert not hasattr(e07_result, "outputs")

    def test_v08_warn_also_fires(self, e07_result) -> None:
        """
        deposit=25,000 is below both 15% (V-07 HARD) and 25% (V-08 WARN).
        The validation pipeline evaluates all rules simultaneously.
        V-08 WARN fires alongside V-07 HARD and appears in ValidationResult.warnings.
        """
        warn_codes = {w.rule_code for w in e07_result.warnings}
        assert warn_codes == e07_expected_warnings()
