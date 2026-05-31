"""
Tests for F-07 — Annual Mortgage Cost.

Formula: annual_mortgage_cost = monthly_mortgage_payment × 12
Source: CALCULATION_SPEC.md F-07.
"""

from decimal import Decimal

import pytest

from app.engine.calculations.formulas import f07_annual_mortgage_cost


class TestF07AnnualMortgageCost:

    def test_e01_reference_value(self) -> None:
        """
        E-01: monthly=593.75 → annual=7125.00.
        Manual: 593.75 × 12 = 7125.00.
        Source: ENGINE_CONTRACTS.md E-01.
        """
        result = f07_annual_mortgage_cost(Decimal("593.75"))
        assert result == Decimal("7125.00")

    def test_e03_reference_value(self) -> None:
        """
        E-03: monthly=1093.75 → annual=13125.00.
        Manual: 1093.75 × 12 = 13125.00.
        Source: ENGINE_CONTRACTS.md E-03.
        """
        result = f07_annual_mortgage_cost(Decimal("1093.75"))
        assert result == Decimal("13125.00")

    def test_zero_monthly_payment(self) -> None:
        """Cash purchase: monthly=0 → annual=0."""
        result = f07_annual_mortgage_cost(Decimal("0"))
        assert result == Decimal("0")

    def test_result_is_decimal(self) -> None:
        """Return type must be Decimal, never float."""
        result = f07_annual_mortgage_cost(Decimal("593.75"))
        assert isinstance(result, Decimal)
