"""
Money value object.

Represents a monetary amount with an explicit currency code.

Design decisions:
- float is explicitly rejected at construction. A float is already imprecise
  before it reaches this class — Decimal(str(float_val)) appears to work but
  silently launders a corrupted value into the domain. The engine's no-float
  invariant (ENGINE_CONTRACTS.md Part 7) is enforced here at the boundary.
- int inputs are accepted and coerced to Decimal via str() to avoid the
  float intermediate that int-to-Decimal conversion can produce on some
  platforms (e.g. Decimal(1000) is safe, but Decimal(0.1) is not).
- Negative amounts are permitted. Cash flow values are legitimately negative
  (DOMAIN_MODEL_ARCHITECTURE.md Part 5.8 — a negative cash flow is a real
  business outcome, not a data error).
- currency defaults to "GBP". Phase 1 is GBP-only. The field exists so that
  code that handles Money values does not implicitly assume a currency —
  making a future multi-currency extension unambiguous.

Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 5.8.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Money:
    """
    An immutable monetary amount with an explicit currency.

    Always use Decimal for the amount. Integer inputs are accepted and
    coerced. Float inputs are rejected with TypeError.

    Examples:
        Money(Decimal("250000"))          purchase price
        Money(Decimal("1250.50"))         monthly rent
        Money(Decimal("-331.90"))         negative annual cash flow
        Money(amount=Decimal("800"))      landlord insurance
        Money(Decimal("0"))               zero refurbishment cost
    """

    amount: Decimal
    currency: str = "GBP"

    def __post_init__(self) -> None:
        # Reject float explicitly — float values are imprecise before they
        # arrive here and must never enter the financial calculation domain.
        if isinstance(self.amount, float):
            raise TypeError(
                f"Money.amount must be Decimal or int, not float. "
                f"Use Decimal('{self.amount}') to be explicit about precision."
            )
        # Coerce int to Decimal. This is safe because int has exact
        # representation — Decimal(str(1000)) == Decimal("1000").
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, "amount", Decimal(str(self.amount)))
