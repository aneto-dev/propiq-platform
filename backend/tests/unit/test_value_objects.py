"""
Unit tests for domain value objects.

Tests domain invariants enforced at construction time.
No infrastructure dependencies — no database, no FastAPI, no ORM.
All tests must pass with Docker stopped.

Covers:
    Money   — Decimal coercion, float rejection, frozen immutability
    Rate    — Decimal fraction conversion, negative value acceptance
              (architecture correction), float rejection, frozen immutability
    PropertyAddress — UK postcode validation, uppercase normalisation,
                      frozen immutability
"""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from app.domain.errors import DomainError
from app.domain.value_objects.address import PropertyAddress
from app.domain.value_objects.money import Money
from app.domain.value_objects.rate import Rate

# ---------------------------------------------------------------------------
# PropertyAddress
# ---------------------------------------------------------------------------


class TestPropertyAddress:
    """Tests for PropertyAddress postcode validation and normalisation."""

    def test_invalid_postcode_raises_domain_error(self) -> None:
        """
        A malformed postcode must raise DomainError at construction.

        Enforces DOMAIN_MODEL_ARCHITECTURE.md Part 5.1: "A PropertyAddress
        with an invalid postcode cannot be constructed."
        """
        with pytest.raises(DomainError):
            PropertyAddress(
                address_line_1="1 Main Street",
                city="London",
                postcode="NOT-A-POSTCODE",
            )

    def test_invalid_postcode_plain_letters_raises(self) -> None:
        """Plain letters with no numeric component are not a valid postcode."""
        with pytest.raises(DomainError):
            PropertyAddress(
                address_line_1="1 Main Street",
                city="Manchester",
                postcode="INVALID",
            )

    def test_valid_postcode_normalised_to_uppercase(self) -> None:
        """
        A valid postcode in lowercase is normalised to uppercase.

        Enforces DOMAIN_MODEL_ARCHITECTURE.md Part 5.1 normalisation rule.
        """
        address = PropertyAddress(
            address_line_1="1 Main Street",
            city="Nottingham",
            postcode="ng1 1aa",
        )
        assert address.postcode == "NG1 1AA"

    def test_valid_postcode_already_uppercase_unchanged(self) -> None:
        """A postcode already in uppercase is accepted and stored as-is."""
        address = PropertyAddress(
            address_line_1="14 Acacia Road",
            city="London",
            postcode="EC1A 1BB",
        )
        assert address.postcode == "EC1A 1BB"

    def test_valid_postcode_without_space_accepted(self) -> None:
        """UK postcodes without a space are valid and accepted."""
        address = PropertyAddress(
            address_line_1="2 Test Lane",
            city="Birmingham",
            postcode="B11AA",
        )
        assert address.postcode.replace(" ", "") == "B11AA"

    def test_address_frozen_raises_on_mutation(self) -> None:
        """
        PropertyAddress is frozen=True and must reject mutation.

        Enforces DOMAIN_MODEL_ARCHITECTURE.md Part 5: value objects are
        immutable by definition.
        """
        address = PropertyAddress(
            address_line_1="1 Main Street",
            city="London",
            postcode="EC1A 1BB",
        )
        with pytest.raises(FrozenInstanceError):
            address.postcode = "W1A 1AA"  # type: ignore[misc]

    def test_optional_address_line_2_defaults_to_none(self) -> None:
        """address_line_2 is optional and defaults to None."""
        address = PropertyAddress(
            address_line_1="1 Main Street",
            city="Leeds",
            postcode="LS1 1AA",
        )
        assert address.address_line_2 is None


# ---------------------------------------------------------------------------
# Rate
# ---------------------------------------------------------------------------


class TestRate:
    """Tests for Rate percentage representation and value constraints."""

    def test_as_decimal_fraction_5_5(self) -> None:
        """
        Rate(5.5).as_decimal_fraction() must return Decimal("0.055").

        This is the roadmap-specified test (Commit 1.6 spec).
        Enforces the percentage-to-fraction convention throughout the engine.
        """
        rate = Rate(Decimal("5.5"))
        assert rate.as_decimal_fraction() == Decimal("0.055")

    def test_as_decimal_fraction_20(self) -> None:
        """Rate(20) represents 20% — as_decimal_fraction returns 0.20."""
        rate = Rate(Decimal("20"))
        assert rate.as_decimal_fraction() == Decimal("0.2")

    def test_as_decimal_fraction_125(self) -> None:
        """Rate(125) represents 125% (ICR threshold) — valid above 100."""
        rate = Rate(Decimal("125"))
        assert rate.as_decimal_fraction() == Decimal("1.25")

    def test_as_decimal_fraction_zero(self) -> None:
        """Rate(0) represents 0% — valid for cash purchase scenarios."""
        rate = Rate(Decimal("0"))
        assert rate.as_decimal_fraction() == Decimal("0")

    def test_negative_rate_accepted(self) -> None:
        """
        Negative Rate values MUST be accepted.

        Architecture correction applied after Commit 1.3: Rate has no
        non-negativity constraint. DOMAIN_MODEL_ARCHITECTURE.md Part 8.3
        explicitly marks cash_on_cash_return_percent and net_yield_percent
        as "(may be negative)". ENGINE_CONTRACTS.md E-03 requires
        cash_on_cash_return_percent = -2.29.

        This test is a regression guard: if the >= 0 constraint is
        accidentally reintroduced, this test will catch it immediately.
        """
        # E-03 exact value — Ltd Co, high leverage scenario
        rate = Rate(Decimal("-2.29"))
        assert rate.value == Decimal("-2.29")
        assert rate.as_decimal_fraction() == Decimal("-0.0229")

    def test_negative_rate_as_decimal_fraction(self) -> None:
        """Negative rate fraction conversion is sign-preserving."""
        rate = Rate(Decimal("-0.66"))
        result = rate.as_decimal_fraction()
        assert result == Decimal("-0.0066")

    def test_int_input_coerced_to_decimal(self) -> None:
        """Integer input is coerced to Decimal exactly."""
        rate = Rate(5)  # type: ignore[arg-type]
        assert isinstance(rate.value, Decimal)
        assert rate.value == Decimal("5")

    def test_float_input_raises_type_error(self) -> None:
        """
        Float input must raise TypeError.

        Floats are imprecise before they arrive. Rate values feed directly
        into financial formulas — float imprecision propagates through every
        downstream calculation.
        """
        with pytest.raises(TypeError):
            Rate(5.5)  # type: ignore[arg-type]

    def test_rate_frozen_raises_on_mutation(self) -> None:
        """Rate is frozen=True and must reject mutation."""
        rate = Rate(Decimal("5.5"))
        with pytest.raises(FrozenInstanceError):
            rate.value = Decimal("6.0")  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------


class TestMoney:
    """Tests for Money Decimal coercion, float rejection, and immutability."""

    def test_int_input_coerced_to_decimal(self) -> None:
        """
        Integer input to Money is coerced to Decimal.

        This is the roadmap-specified test (Commit 1.6 spec).
        Money(1000) must produce Money(Decimal("1000")), not int 1000.
        """
        money = Money(1000)  # type: ignore[arg-type]
        assert isinstance(money.amount, Decimal)
        assert money.amount == Decimal("1000")

    def test_decimal_input_stored_exactly(self) -> None:
        """Decimal input is stored without modification."""
        money = Money(Decimal("200000.50"))
        assert money.amount == Decimal("200000.50")
        assert isinstance(money.amount, Decimal)

    def test_negative_amount_accepted(self) -> None:
        """
        Negative Money values are valid for cash flow fields.

        DOMAIN_MODEL_ARCHITECTURE.md Part 5.8: "Cash flow values may be
        negative and are valid negative Money values."
        """
        money = Money(Decimal("-331.90"))
        assert money.amount == Decimal("-331.90")

    def test_zero_amount_accepted(self) -> None:
        """Zero is a valid monetary amount."""
        money = Money(Decimal("0"))
        assert money.amount == Decimal("0")

    def test_float_input_raises_type_error(self) -> None:
        """
        Float input must raise TypeError.

        Floats are imprecise before construction. A float monetary value
        has already lost precision before Money can see it.
        """
        with pytest.raises(TypeError):
            Money(200000.50)  # type: ignore[arg-type]

    def test_default_currency_is_gbp(self) -> None:
        """Default currency is GBP — Phase 1 is UK-only."""
        money = Money(Decimal("100"))
        assert money.currency == "GBP"

    def test_money_frozen_raises_on_mutation(self) -> None:
        """Money is frozen=True and must reject mutation."""
        money = Money(Decimal("100"))
        with pytest.raises(FrozenInstanceError):
            money.amount = Decimal("200")  # type: ignore[misc]
