"""
CalculationService integration tests — end-to-end calculation pipeline.

Roadmap-specified tests (IMPLEMENTATION_ROADMAP.md Commit 5.6):
  1. Successful calculation matches E-01 outputs
  2. Validation failure: returns CalculationValidationFailure with error codes
  3. Ownership failure: raises NotFoundError
  4. Calculation on ARCHIVED deal: raises DomainError

This is the first true end-to-end test:
  Deal → ConfigurationService → Engine → SnapshotService → Database → Result

Output assertions (key E-01 fields via verified field paths):
  annual_cash_flow_gbp.amount  == Decimal("-331.90")   (Money.amount)
  gross_annual_rent_gbp.amount == Decimal("11400.00")  (Money.amount)
  total_cash_deployed_gbp.amount == Decimal("60000.00") (Money.amount)
  ltv_percent.value            == Decimal("75.00")     (Rate.value)

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 5.
    IMPLEMENTATION_ROADMAP.md Commit 5.6.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.domain.enums import (
    DealStatus,
    IncomeTaxBand,
    MortgageType,
    OwnershipStructure,
    PropertyCountry,
    PropertyType,
    Tenure,
)
from app.domain.errors import DomainError, NotFoundError
from app.domain.value_objects.address import PropertyAddress
from app.repositories.configuration_repository import ConfigurationRepository
from app.repositories.deal_repository import DealRepository
from app.repositories.property_repository import PropertyRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.services.calculation_service import (
    CalculationService,
    CalculationSuccess,
    CalculationValidationFailure,
)
from app.services.configuration_service import (
    ConfigurationService,
    RawCalculationInputs,
)
from app.services.deal_service import DealService
from app.services.property_service import PropertyService
from app.services.snapshot_service import make_snapshot_service
from app.services.user_service import UserService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CALCULATION_DATE = date(2025, 6, 1)


def _e01_raw_inputs() -> RawCalculationInputs:
    """E-01 inputs as RawCalculationInputs (no optional override defaults)."""
    return RawCalculationInputs(
        purchase_price=Decimal("200000"),
        monthly_rent=Decimal("950"),
        deposit_amount=Decimal("50000"),
        mortgage_interest_rate=Decimal("4.75"),
        mortgage_term_years=25,
        mortgage_type=MortgageType.INTEREST_ONLY,
        ownership_structure=OwnershipStructure.INDIVIDUAL,
        income_tax_band=IncomeTaxBand.BASIC_RATE,
        is_additional_dwelling=True,
        property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
        tenure=Tenure.FREEHOLD,
        property_country=PropertyCountry.ENGLAND,
        postcode="NG1 1AA",
        # No optional overrides — all will use config defaults
    )


def _invalid_inputs() -> RawCalculationInputs:
    """Inputs that trigger V-07 HARD failure (deposit < 15% of purchase price)."""
    return RawCalculationInputs(
        purchase_price=Decimal("200000"),
        monthly_rent=Decimal("950"),
        deposit_amount=Decimal("25000"),  # 12.5% — below V-07 threshold
        mortgage_interest_rate=Decimal("4.75"),
        mortgage_term_years=25,
        mortgage_type=MortgageType.INTEREST_ONLY,
        ownership_structure=OwnershipStructure.INDIVIDUAL,
        income_tax_band=IncomeTaxBand.BASIC_RATE,
        is_additional_dwelling=True,
        property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
        tenure=Tenure.FREEHOLD,
        property_country=PropertyCountry.ENGLAND,
        postcode="NG1 1AA",
    )


def _make_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create a NullPool session factory for AuditService.write_failure()."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(
        get_settings().test_database_url,
        echo=False,
        poolclass=NullPool,
    )
    return async_sessionmaker(engine, expire_on_commit=False)


def _make_calculation_service(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> CalculationService:
    config_repo = ConfigurationRepository(session)
    return CalculationService(
        session=session,
        deal_repo=DealRepository(session),
        config_service=ConfigurationService(config_repo),
        snapshot_service=make_snapshot_service(session),
        audit_service=AuditService(session_factory=session_factory),
    )


async def _setup_user_property_deal(
    session: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Create user, property, deal — return (user_id, property_id, deal_id)."""
    user_svc = UserService(UserRepository(session))
    user = await user_svc.get_or_create_user(
        supabase_auth_id=uuid.uuid4(),
        email=f"calc_test_{uuid.uuid4().hex[:8]}@example.com",
    )
    await session.commit()

    prop_svc = PropertyService(PropertyRepository(session))
    prop = await prop_svc.create_property(
        user_id=user.id,
        address=PropertyAddress(
            address_line_1="14 Acacia Road",
            city="Nottingham",
            postcode="NG1 1AA",
        ),
        property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
        tenure=Tenure.FREEHOLD,
        lease_years_remaining=None,
        bedrooms=None,
        epc_rating=None,
    )
    await session.commit()

    deal_svc = DealService(
        deal_repo=DealRepository(session),
        property_repo=PropertyRepository(session),
        profile_repo=__import__(
            "app.repositories.investor_profile_repository",
            fromlist=["InvestorProfileRepository"],
        ).InvestorProfileRepository(session),
    )
    deal = await deal_svc.create_deal(
        user_id=user.id,
        property_id=prop.id,
        label="E-01 Test Deal",
    )
    await session.commit()

    return user.id, prop.id, deal.id


# ---------------------------------------------------------------------------
# Test 1 — Successful calculation matches E-01 outputs
# IMPLEMENTATION_ROADMAP.md Commit 5.6 test 1
# ---------------------------------------------------------------------------


class TestSuccessfulCalculation:
    """Full end-to-end pipeline: deal → engine → snapshot → DB → result."""

    async def test_full_calculation_pipeline_e01(
        self, async_session: AsyncSession
    ) -> None:
        """
        Successful E-01 calculation returns CalculationSuccess with correct
        output values persisted and loaded from the database.
        IMPLEMENTATION_ROADMAP.md Commit 5.6 — end-to-end integration test.
        """
        session_factory = _make_session_factory()
        user_id, _, deal_id = await _setup_user_property_deal(async_session)

        svc = _make_calculation_service(async_session, session_factory)
        result = await svc.run_calculation(
            user_id=user_id,
            deal_id=deal_id,
            raw_inputs=_e01_raw_inputs(),
            calculation_date=CALCULATION_DATE,
        )

        # Assert result type
        assert isinstance(result, CalculationSuccess), (
            f"Expected CalculationSuccess, got {type(result)}"
        )
        assert result.deal_status_after == DealStatus.ANALYSED
        assert result.snapshot_id is not None

        # Assert key E-01 output values via snapshot summary
        # (ENGINE_CONTRACTS.md E-01 expected outputs)
        summary = result.snapshot_summary
        assert summary.outputs.annual_cash_flow_gbp.amount == Decimal("-331.90")
        assert summary.outputs.gross_annual_rent_gbp.amount == Decimal("11400.00")
        assert summary.outputs.total_cash_deployed_gbp.amount == Decimal("60000.00")
        assert summary.outputs.ltv_percent.value == Decimal("75.00")

    async def test_deal_status_updated_to_analysed(
        self, async_session: AsyncSession
    ) -> None:
        """After successful calculation, deal status in DB is ANALYSED."""
        session_factory = _make_session_factory()
        user_id, _, deal_id = await _setup_user_property_deal(async_session)

        svc = _make_calculation_service(async_session, session_factory)
        result = await svc.run_calculation(
            user_id=user_id,
            deal_id=deal_id,
            raw_inputs=_e01_raw_inputs(),
            calculation_date=CALCULATION_DATE,
        )

        assert isinstance(result, CalculationSuccess)

        # Reload deal and verify status in DB
        deal = await DealRepository(async_session).find_by_id_for_user(deal_id, user_id)
        assert deal is not None
        assert deal.status == DealStatus.ANALYSED


# ---------------------------------------------------------------------------
# Test 2 — Validation failure
# IMPLEMENTATION_ROADMAP.md Commit 5.6 test 2
# ---------------------------------------------------------------------------


class TestValidationFailure:
    """Validation failure returns CalculationValidationFailure with error codes."""

    async def test_validation_failure_returns_structured_errors(
        self, async_session: AsyncSession
    ) -> None:
        """
        Invalid inputs (deposit < 15% → V-07 HARD) returns
        CalculationValidationFailure with the correct rule code.
        IMPLEMENTATION_ROADMAP.md Commit 5.6 test 2.
        """
        session_factory = _make_session_factory()
        user_id, _, deal_id = await _setup_user_property_deal(async_session)

        svc = _make_calculation_service(async_session, session_factory)
        result = await svc.run_calculation(
            user_id=user_id,
            deal_id=deal_id,
            raw_inputs=_invalid_inputs(),
            calculation_date=CALCULATION_DATE,
        )

        assert isinstance(result, CalculationValidationFailure), (
            f"Expected CalculationValidationFailure, got {type(result)}"
        )
        rule_codes = [e.rule_code for e in result.hard_errors]
        assert "V-07" in rule_codes


# ---------------------------------------------------------------------------
# Test 3 — Ownership failure
# IMPLEMENTATION_ROADMAP.md Commit 5.6 test 3
# ---------------------------------------------------------------------------


class TestOwnershipFailure:
    """Wrong user_id raises NotFoundError."""

    async def test_ownership_failure_raises_not_found(
        self, async_session: AsyncSession
    ) -> None:
        """
        run_calculation() with a user_id that does not own the deal raises
        NotFoundError.
        IMPLEMENTATION_ROADMAP.md Commit 5.6 test 3.
        """
        session_factory = _make_session_factory()
        _, _, deal_id = await _setup_user_property_deal(async_session)
        wrong_user_id = uuid.uuid4()

        svc = _make_calculation_service(async_session, session_factory)

        with pytest.raises(NotFoundError) as exc_info:
            await svc.run_calculation(
                user_id=wrong_user_id,
                deal_id=deal_id,
                raw_inputs=_e01_raw_inputs(),
                calculation_date=CALCULATION_DATE,
            )

        assert exc_info.value.entity == "deal"


# ---------------------------------------------------------------------------
# Test 4 — Archived deal
# IMPLEMENTATION_ROADMAP.md Commit 5.6 test 4
# ---------------------------------------------------------------------------


class TestArchivedDeal:
    """Calculation on ARCHIVED deal raises DomainError."""

    async def test_archived_deal_raises_domain_error(
        self, async_session: AsyncSession
    ) -> None:
        """
        run_calculation() on an ARCHIVED deal raises DomainError.
        IMPLEMENTATION_ROADMAP.md Commit 5.6 test 4.
        """
        session_factory = _make_session_factory()
        user_id, _, deal_id = await _setup_user_property_deal(async_session)

        # Archive the deal
        deal_svc = DealService(
            deal_repo=DealRepository(async_session),
            property_repo=PropertyRepository(async_session),
            profile_repo=__import__(
                "app.repositories.investor_profile_repository",
                fromlist=["InvestorProfileRepository"],
            ).InvestorProfileRepository(async_session),
        )
        await deal_svc.archive_deal(user_id=user_id, deal_id=deal_id)
        await async_session.commit()

        svc = _make_calculation_service(async_session, session_factory)

        with pytest.raises(DomainError):
            await svc.run_calculation(
                user_id=user_id,
                deal_id=deal_id,
                raw_inputs=_e01_raw_inputs(),
                calculation_date=CALCULATION_DATE,
            )
