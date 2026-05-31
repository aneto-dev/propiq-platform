"""
Domain enumerations.

All enums used by the domain, engine, and persistence layers are defined
here. Every layer imports from this single module, ensuring consistent
string values across Python code, the database, and the API.

All enums inherit from (str, Enum) so that:
  - Values serialise directly to their string representation in JSON
    without custom encoders (FastAPI / Pydantic v2 handle this natively).
  - SQLAlchemy Enum columns store and retrieve the plain string value.
  - Comparisons with raw strings work: OwnershipStructure.INDIVIDUAL == "INDIVIDUAL"

Only stdlib imports. No application dependencies.

Source: DATABASE_SCHEMA_DESIGN.md Section 1 — Enum Type Definitions.
"""

from enum import Enum


class OwnershipStructure(str, Enum):
    """
    Legal ownership structure under which the property is held.

    Determines the tax calculation pathway:
      INDIVIDUAL      → Tax Pathway A (Section 24 mortgage interest
                        restriction applies from April 2020)
      LIMITED_COMPANY → Tax Pathway B (Corporation Tax; mortgage interest
                        remains fully deductible as a business expense)

    Architecture: CALCULATION_SPEC.md Tax Calculations.
    DOMAIN_MODEL_ARCHITECTURE.md Part 5.5.
    """

    INDIVIDUAL = "INDIVIDUAL"
    LIMITED_COMPANY = "LIMITED_COMPANY"


class IncomeTaxBand(str, Enum):
    """
    Investor's marginal income tax band.

    Required when ownership_structure = INDIVIDUAL.
    Must be None / absent for LIMITED_COMPANY (domain invariant I-06).

    Determines the gross income tax liability and the magnitude of the
    Section 24 mortgage interest tax credit.

    Effective rates: BASIC_RATE = 20%, HIGHER_RATE = 40%, ADDITIONAL_RATE = 45%.

    Architecture: CALCULATION_SPEC.md Tax Pathway A.
    DOMAIN_MODEL_ARCHITECTURE.md Part 5.6.
    """

    BASIC_RATE = "BASIC_RATE"
    HIGHER_RATE = "HIGHER_RATE"
    ADDITIONAL_RATE = "ADDITIONAL_RATE"


class MortgageType(str, Enum):
    """
    Mortgage repayment structure.

    Determines two separate formula pathways:
      INTEREST_ONLY — monthly payment is interest only (F-06a).
                      Annual mortgage interest = annual mortgage cost.
      REPAYMENT     — monthly payment includes capital (F-06b).
                      Only the interest component (F-08) is tax-deductible.

    Architecture: CALCULATION_SPEC.md F-06, F-08.
    DOMAIN_MODEL_ARCHITECTURE.md Part 5.7.
    """

    INTEREST_ONLY = "INTEREST_ONLY"
    REPAYMENT = "REPAYMENT"


class PropertyType(str, Enum):
    """
    Classification of the investment property.

    Phase 1 supports RESIDENTIAL_SINGLE_LET only.
    Any other value produces HARD validation failure V-15.

    Future phases will extend this enum:
      HMO                    — Phase 3 (per-room income modelling)
      MULTI_UNIT_FREEHOLD_BLOCK — Phase 3+

    Architecture: DATABASE_SCHEMA_DESIGN.md Section 1 — property_type_enum.
    CALCULATION_SPEC.md V-15.
    """

    RESIDENTIAL_SINGLE_LET = "RESIDENTIAL_SINGLE_LET"


class Tenure(str, Enum):
    """
    Property tenure type.

    LEASEHOLD triggers additional required inputs:
      - annual_service_charge
      - annual_ground_rent
      - lease_years_remaining (on the property record)

    LEASEHOLD with lease_years_remaining < 80 triggers risk flag
    LEASEHOLD_SHORT_LEASE (MEDIUM severity).

    Architecture: CALCULATION_SPEC.md V-21, V-22, V-23;
    Risk flag LEASEHOLD_SHORT_LEASE.
    DOMAIN_MODEL_ARCHITECTURE.md Part 5.10.
    """

    FREEHOLD = "FREEHOLD"
    LEASEHOLD = "LEASEHOLD"


class PropertyCountry(str, Enum):
    """
    Country in which the property is located.

    Phase 1 supports ENGLAND only. Any other value produces
    HARD validation failure V-16 (different land transaction
    tax regimes — LBTT in Scotland, LTT in Wales — are not
    yet implemented).

    Future phases will extend this enum:
      SCOTLAND        — Phase 3+ (LBTT)
      WALES           — Phase 3+ (LTT)
      NORTHERN_IRELAND — Phase 3+

    Architecture: DATABASE_SCHEMA_DESIGN.md Section 1 — property_country_enum.
    CALCULATION_SPEC.md V-16.
    """

    ENGLAND = "ENGLAND"


class DealStatus(str, Enum):
    """
    Current lifecycle stage of a deal in the investor's pipeline.

    Phase 1 values only. Phase 2 adds operational workflow stages:
      OFFER_SUBMITTED, PURCHASED, HELD, EXITED
    per ROADMAP.md Phase 2 and DOMAIN_MODEL_ARCHITECTURE.md Part 19.1.

    Transition rules (enforced by DealStatusTransitionService):
      DRAFT    → ANALYSED   first calculation completed
      DRAFT    → ARCHIVED   user abandons a draft deal
      ANALYSED → ARCHIVED   user archives a completed deal
      ARCHIVED → any        NOT permitted

    Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 4.4 and Part 5.2.
    """

    DRAFT = "DRAFT"
    ANALYSED = "ANALYSED"
    ARCHIVED = "ARCHIVED"


class UserStatus(str, Enum):
    """
    Account status of a platform user.

    ARCHIVED is the GDPR anonymisation terminal state (Phase 2):
    PII columns are cleared but the user record is retained for
    referential integrity with historical snapshot records.

    Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 4.1.
    AUTHORIZATION_MODEL.md Part 4.1.
    """

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"


class CalculationOutcome(str, Enum):
    """
    Result classification of a single calculation attempt.

    Stored on every audit_calculations row, regardless of outcome.
    Exactly one audit record is written per calculation attempt (SI-05).

      SUCCESS            engine returned EngineResult; snapshot created
      VALIDATION_FAILURE engine returned ValidationResult(is_valid=False);
                         hard_errors recorded; no snapshot created
      ENGINE_ERROR       unexpected engine failure; sanitised error_detail
                         recorded; no snapshot created

    Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 7, 8, 9.
    OBSERVABILITY_ARCHITECTURE.md Part 6.2.
    """

    SUCCESS = "SUCCESS"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    ENGINE_ERROR = "ENGINE_ERROR"


class InputSource(str, Enum):
    """
    Provenance of an optional input value used in a calculation.

    Stored alongside every optional input in snapshot_inputs via
    paired _source columns (e.g. void_rate_percent_source).

    Enforces ADR-009 (assumption provenance must be recorded) and
    ADR-013 (user overrides always take precedence over platform defaults).

      USER_OVERRIDE  the investor explicitly provided this value for this deal
      CONFIG_DEFAULT the active assumption configuration default was applied

    Extended in Phase 3+ with EXTERNAL_PROVIDER (area intelligence),
    and Phase 5+ with AI_SUGGESTION (must be explicitly confirmed by
    the user before being promoted to USER_OVERRIDE).

    Architecture: DATABASE_SCHEMA_DESIGN.md — input_source_enum.
    PERSISTENCE_ARCHITECTURE.md Part 18.
    """

    USER_OVERRIDE = "USER_OVERRIDE"
    CONFIG_DEFAULT = "CONFIG_DEFAULT"


class FlagSeverity(str, Enum):
    """
    Severity classification of a risk flag.

    All flags are informational — none block snapshot creation or
    prevent a deal from proceeding.

      HIGH    materially affects deal viability; requires immediate attention
      MEDIUM  warrants review; may affect financing or net returns
      INFO    contextual disclosure; no immediate action required

    Architecture: CALCULATION_SPEC.md Risk Flag Definitions.
    ENGINE_CONTRACTS.md Part 5.
    DOMAIN_MODEL_ARCHITECTURE.md Part 12.
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    INFO = "INFO"
