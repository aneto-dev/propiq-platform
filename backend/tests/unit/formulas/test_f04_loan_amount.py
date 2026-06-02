"""
Tests for F-04 — Loan Amount.

Formula: loan_amount = purchase_price - deposit_amount
Source: CALCULATION_SPEC.md F-04.
"""

from decimal import Decimal

from app.engine.calculations.formulas import f04_loan_amount


class TestF04LoanAmount:

    def test_e01_reference_value(self) -> None:
        """
        E-01 scenario: purchase=200000, deposit=50000 → loan=150000.
        Manual: 200000 - 50000 = 150000.
        Source: ENGINE_CONTRACTS.md E-01.
        """
        result = f04_loan_amount(Decimal("200000"), Decimal("50000"))
        assert result == Decimal("150000")

    def test_e03_reference_value(self) -> None:
        """
        E-03 scenario: purchase=350000, deposit=87500 → loan=262500.
        Manual: 350000 - 87500 = 262500.
        Source: ENGINE_CONTRACTS.md E-03.
        """
        result = f04_loan_amount(Decimal("350000"), Decimal("87500"))
        assert result == Decimal("262500")

    def test_cash_purchase_zero_loan(self) -> None:
        """Full deposit (cash purchase) → loan amount is zero."""
        result = f04_loan_amount(Decimal("200000"), Decimal("200000"))
        assert result == Decimal("0")

    def test_twenty_five_percent_deposit(self) -> None:
        """
        25% deposit on £300,000 property → loan £225,000.
        Manual: 300000 - 75000 = 225000.
        """
        result = f04_loan_amount(Decimal("300000"), Decimal("75000"))
        assert result == Decimal("225000")

    def test_result_is_decimal(self) -> None:
        """Return type must be Decimal, never float."""
        result = f04_loan_amount(Decimal("200000"), Decimal("50000"))
        assert isinstance(result, Decimal)
