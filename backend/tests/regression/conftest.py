"""
Regression-level test fixtures and helpers.

Imports all scenario builders and expected-value functions from the
top-level conftest and provides the assert_outputs helper used by
every regression test.

Source: TEST_STRATEGY.md Part 7.3.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# Re-export all scenario builders for regression test imports
from tests.conftest import (  # noqa: F401
    REFERENCE_CONFIG,
    e01_absent_flags,
    e01_expected_flags,
    e01_expected_outputs,
    e01_expected_warnings,
    e01_input,
    e02_absent_flags,
    e02_expected_flags,
    e02_expected_outputs,
    e02_expected_warnings,
    e02_input,
    e03_absent_flags,
    e03_expected_flags,
    e03_expected_outputs,
    e03_expected_warnings,
    e03_input,
    e04_absent_flags,
    e04_expected_flags,
    e04_expected_outputs,
    e04_expected_warnings,
    e04_input,
    e05_absent_flags,
    e05_expected_flags,
    e05_expected_outputs,
    e05_expected_warnings,
    e05_input,
    e06_absent_flags,
    e06_expected_flags,
    e06_expected_outputs,
    e06_expected_warnings,
    e06_input,
    e07_expected_hard_error_code,
    e07_input,
    e08_absent_flags,
    e08_expected_flags,
    e08_expected_warnings,
    e08_input,
    e09_expected_flags,
    e09_input,
    e10_expected_flags,
    e10_expected_outputs,
    e10_expected_warnings,
    e10_input,
    e11_absent_flags,
    e11_expected_flags,
    e11_expected_outputs,
    e11_expected_warnings,
    e11_input,
    e12_absent_flags,
    e12_expected_flags,
    e12_expected_outputs,
    e12_expected_warnings,
    e12_input,
)

_TWO_DP = Decimal("0.01")


def r2(value: Decimal) -> Decimal:
    """Round to 2dp ROUND_HALF_UP — matches ENGINE_CONTRACTS.md Part 7.2."""
    return value.quantize(_TWO_DP, rounding=ROUND_HALF_UP)


def assert_outputs(
    actual_outputs: object,
    expected: dict[str, object],
) -> None:
    """
    Assert every field in expected matches the corresponding field on
    actual_outputs, rounded to 2dp where both are Decimal.

    Produces a descriptive failure message that includes the field name,
    the expected value, and the actual value.

    Source: TEST_STRATEGY.md Part 7.3.
    """
    for field_name, expected_val in expected.items():
        actual_val = getattr(actual_outputs, field_name)
        if isinstance(expected_val, Decimal) and isinstance(actual_val, Decimal):
            actual_rounded = r2(actual_val)
            assert actual_rounded == expected_val, (
                f"Field {field_name!r}: "
                f"expected {expected_val}, got {actual_rounded} "
                f"(raw: {actual_val})"
            )
        elif expected_val is None:
            assert actual_val is None, (
                f"Field {field_name!r}: expected None, got {actual_val!r}"
            )
        else:
            assert actual_val == expected_val, (
                f"Field {field_name!r}: expected {expected_val!r}, "
                f"got {actual_val!r}"
            )


def assert_flags_present(
    actual_flags: list,
    expected_codes: frozenset[str],
) -> None:
    """Assert every code in expected_codes appears in actual_flags."""
    actual_codes = {f.code for f in actual_flags}
    missing = expected_codes - actual_codes
    assert not missing, (
        "Expected flags not present: "
        + str(sorted(missing))
        + " | Actual: "
        + str(sorted(actual_codes))
    )


def assert_flags_absent(
    actual_flags: list,
    absent_codes: frozenset[str],
) -> None:
    """Assert no code in absent_codes appears in actual_flags."""
    actual_codes = {f.code for f in actual_flags}
    unexpected = absent_codes & actual_codes
    assert not unexpected, (
        "Flags present but should be absent: "
        + str(sorted(unexpected))
        + " | Actual: "
        + str(sorted(actual_codes))
    )


def assert_warnings(
    actual_warnings: list,
    expected_codes: frozenset[str],
) -> None:
    """Assert warning rule codes match expected set exactly."""
    actual_codes = {w.rule_code for w in actual_warnings}
    assert actual_codes == expected_codes, (
        "Validation warnings mismatch. Expected: "
        + str(sorted(expected_codes))
        + " | Actual: "
        + str(sorted(actual_codes))
    )
