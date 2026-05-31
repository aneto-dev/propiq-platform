"""
Rate value object.

Represents a percentage rate stored in human-readable percentage form.

Convention (enforced throughout this codebase):
    Rate(Decimal("5.5"))  means 5.5%,  not 0.055
    Rate(Decimal("20"))   means 20%,   not 0.20
    Rate(Decimal("125"))  means 125%   (valid — used for ICR thresholds)

The as_decimal_fraction() method converts to the arithmetic form (÷100)
for use in formula calculations. All formula functions in the engine
receive Rate values and call as_decimal_fraction() internally — they never
receive raw floats or ambiguous numerics.

Design decisions:
- float is rejected for the same reason as Money — float values are
  imprecise before they arrive and must not enter the calculation domain.
- int inputs are coerced to Decimal via str() for exact representation.
- value must be >= 0. A negative percentage rate has no meaning in this
  domain (no negative interest rates, no negative yield, no negative
  VAT rate). Upper bound is not enforced: valid rates include ICR
  thresholds (125%, 145%), stress test rates (5.5%), and standard
  percentages (20% VAT, 3% SDLT surcharge). Capping at 100 would
  prevent legitimate values.

Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 5.9.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Rate:
    """
    An immutable percentage rate.

    Stored as a percentage value — 5.5 means 5.5%, not 0.055.
    Use as_decimal_fraction() to obtain the arithmetic form for calculations.

    Examples:
        Rate(Decimal("5.5"))    mortgage interest rate of 5.5%
        Rate(Decimal("3.85"))   void rate of 3.85%
        Rate(Decimal("20"))     VAT rate of 20%
        Rate(Decimal("125"))    ICR threshold of 125%
        Rate(Decimal("0"))      zero rate (cash purchase, no interest)
    """

    value: Decimal

    def __post_init__(self) -> None:
        # Reject float — same rationale as Money. Rates feed directly into
        # financial formulas; imprecision introduced here propagates through
        # every downstream calculation.
        if isinstance(self.value, float):
            raise TypeError(
                f"Rate.value must be Decimal or int, not float. "
                f"Use Decimal('{self.value}') to be explicit about precision."
            )
        # Coerce int to Decimal.
        if not isinstance(self.value, Decimal):
            object.__setattr__(self, "value", Decimal(str(self.value)))

        # Validate non-negative. A negative percentage rate has no meaning
        # in this domain. Check after coercion so the comparison is always
        # Decimal vs Decimal.
        if self.value < Decimal("0"):
            raise ValueError(
                f"Rate.value must be >= 0, got {self.value}. "
                f"Negative percentage rates are not valid in this domain."
            )

    def as_decimal_fraction(self) -> Decimal:
        """
        Return the rate as a decimal fraction for arithmetic use.

        Rate(Decimal("5.5")).as_decimal_fraction() → Decimal("0.055")
        Rate(Decimal("20")).as_decimal_fraction()  → Decimal("0.20")
        Rate(Decimal("0")).as_decimal_fraction()   → Decimal("0")

        Use this in formula calculations, never the raw .value.
        """
        return self.value / Decimal("100")
