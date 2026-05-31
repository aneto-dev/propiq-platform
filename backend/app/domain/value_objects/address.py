"""
PropertyAddress value object.

Represents a validated UK property address. Postcode validation is performed
at construction time using a regex. No external postcode lookup service is
used — that is a Phase 3+ concern (area intelligence integration).

Validation behaviour:
- Postcodes are normalised to uppercase with a single internal space
  (e.g. "ng1 1aa" → "NG1 1AA"). The regex permits optional whitespace
  between the outward and inward codes; normalisation standardises storage.
- An invalid postcode raises DomainError immediately. This enforces the
  domain invariant at the boundary — a PropertyAddress with an invalid
  postcode cannot be constructed.

Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 5.1.
DATABASE_SCHEMA_DESIGN.md — properties.postcode CHECK constraint.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.enums import PropertyCountry
from app.domain.errors import DomainError

# ---------------------------------------------------------------------------
# UK postcode regex
# ---------------------------------------------------------------------------
# Covers all valid Royal Mail postcode formats:
#   AN NAA    e.g. W1 1AA
#   ANN NAA   e.g. W12 1AA
#   AAN NAA   e.g. SW1 1AA
#   AANN NAA  e.g. SW1W 1AA
#   ANA NAA   e.g. W1A 1AA
#   AANA NAA  e.g. EC1A 1AA
#
# Whitespace between the outward (left) and inward (right) parts is
# optional to accept both "NG1 1AA" and "NG11AA". After validation the
# postcode is normalised to include exactly one space.
#
# re.IGNORECASE is set so "ng1 1aa" is accepted; __post_init__ normalises
# the final stored value to uppercase.
_UK_POSTCODE_RE = re.compile(
    r"^[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2}$",
    re.IGNORECASE,
)


def _normalise_postcode(postcode: str) -> str:
    """
    Strip, uppercase, and insert a single space between outward and inward codes.

    "ng11aa"  → "NG1 1AA"
    "NG1 1AA" → "NG1 1AA"
    "ng1  1aa"→ "NG1 1AA"
    """
    stripped = postcode.strip().upper().replace(" ", "")
    # The inward code is always 3 characters (digit + 2 letters).
    # Insert a space before the last 3 characters to produce the
    # canonical "outward inward" form.
    return f"{stripped[:-3]} {stripped[-3:]}"


@dataclass(frozen=True)
class PropertyAddress:
    """
    An immutable, validated UK property address.

    Postcode is validated against the UK Royal Mail format regex and
    normalised to uppercase with a single space at construction.

    Fields with defaults must follow fields without defaults — Python
    dataclass ordering requires required fields first.

    Examples:
        PropertyAddress(
            address_line_1="14 Acacia Road",
            city="Nottingham",
            postcode="NG1 1AA",
        )

        PropertyAddress(
            address_line_1="Flat 3",
            address_line_2="22 Victoria Street",
            city="London",
            postcode="sw1a 1aa",   # normalised to "SW1A 1AA"
        )
    """

    address_line_1: str
    city: str
    postcode: str
    address_line_2: str | None = None
    country: PropertyCountry = PropertyCountry.ENGLAND

    def __post_init__(self) -> None:
        # Validate postcode format before normalisation.
        raw = self.postcode.strip()
        if not _UK_POSTCODE_RE.match(raw):
            raise DomainError(
                f"Invalid UK postcode format: '{self.postcode}'. "
                f"Expected format examples: NG1 1AA, SW1A 1AA, W1 1AA."
            )
        # Normalise to uppercase with a single internal space and store.
        # object.__setattr__ is required because the dataclass is frozen —
        # normal attribute assignment raises FrozenInstanceError.
        object.__setattr__(self, "postcode", _normalise_postcode(raw))
