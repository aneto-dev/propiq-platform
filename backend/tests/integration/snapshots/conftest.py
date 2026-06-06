"""
Shared fixtures for snapshot integration tests.

Provides a pre-built E-01 CalculationSnapshot and the supporting
user/property/deal records required to satisfy FK constraints.

The snapshot is constructed directly from E-01 values (hardcoded from
ENGINE_CONTRACTS.md Part 11) without running the engine, so these tests
verify the repository mapping in isolation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.deal import Deal, DealWorkingInputs
from app.domain.entities.property import Property
from app.domain.entities.snapshot import (
    CalculationSnapshot,
    ConfigVersionRefs,
    RiskFlag,
    SDLTBandResult,
    SnapshotInputs,
    SnapshotIntermediates,
    SnapshotOutputs,
    ValidationWarning,
)
from app.domain.entities.user import User
from app.domain.enums import (
    DealStatus,
    FlagSeverity,
    IncomeTaxBand,
    InputSource,
    MortgageType,
    OwnershipStructure,
    PropertyCountry,
    PropertyType,
    Tenure,
    UserStatus,
)
from app.domain.value_objects.address import PropertyAddress
from app.domain.value_objects.money import Money
from app.domain.value_objects.rate import Rate
from app.repositories.deal_repository import DealRepository
from app.repositories.property_repository import PropertyRepository
from app.repositories.user_repository import UserRepository

# ---------------------------------------------------------------------------
# DB record helpers
# ---------------------------------------------------------------------------

async def create_user(session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        supabase_auth_id=uuid.uuid4(),
        email=f"snap_test_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Snapshot Test User",
        status=UserStatus.ACTIVE,
    )
    await UserRepository(session).save(user)
    await session.commit()
    return user


async def create_property(session: AsyncSession, user_id: uuid.UUID) -> Property:
    prop = Property(
        id=uuid.uuid4(),
        user_id=user_id,
        address=PropertyAddress(
            address_line_1="14 Acacia Road",
            city="Nottingham",
            postcode="NG1 1AA",
        ),
        property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
        tenure=Tenure.FREEHOLD,
    )
    await PropertyRepository(session).save(prop)
    await session.commit()
    return prop


async def create_deal(
    session: AsyncSession, user_id: uuid.UUID, property_id: uuid.UUID
) -> Deal:
    deal = Deal(
        id=uuid.uuid4(),
        user_id=user_id,
        property_id=property_id,
        label="E-01 Deal",
        status=DealStatus.DRAFT,
        working_inputs=DealWorkingInputs(),
    )
    await DealRepository(session).save(deal)
    await session.commit()
    return deal


async def get_config_ids(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Return (assumption_id, sdlt_id, ct_id) from the seeded config tables."""
    from sqlalchemy import text

    r1 = await session.execute(
        text("SELECT id FROM config_assumption_versions LIMIT 1")
    )
    r2 = await session.execute(
        text("SELECT id FROM config_sdlt_versions LIMIT 1")
    )
    r3 = await session.execute(
        text("SELECT id FROM config_corporation_tax_versions LIMIT 1")
    )
    row1, row2, row3 = r1.fetchone(), r2.fetchone(), r3.fetchone()
    assert row1 and row2 and row3, "Config seed data missing"
    return uuid.UUID(str(row1[0])), uuid.UUID(str(row2[0])), uuid.UUID(str(row3[0]))


# ---------------------------------------------------------------------------
# E-01 snapshot builder
# Values from ENGINE_CONTRACTS.md Part 11 — E-01 Baseline (Basic Rate Individual)
# ---------------------------------------------------------------------------

def make_e01_snapshot(
    deal_id: uuid.UUID,
    user_id: uuid.UUID,
    assumption_id: uuid.UUID,
    sdlt_id: uuid.UUID,
    ct_id: uuid.UUID,
    snapshot_id: uuid.UUID | None = None,
) -> CalculationSnapshot:
    """Build a complete E-01 CalculationSnapshot domain entity."""
    sid = snapshot_id or uuid.uuid4()

    inputs = SnapshotInputs(
        purchase_price=Money(Decimal("200000")),
        monthly_rent=Money(Decimal("950")),
        deposit_amount=Money(Decimal("50000")),
        mortgage_interest_rate=Rate(Decimal("4.5")),
        mortgage_term_years=25,
        mortgage_type=MortgageType.INTEREST_ONLY,
        ownership_structure=OwnershipStructure.INDIVIDUAL,
        income_tax_band=IncomeTaxBand.BASIC_RATE,
        is_additional_dwelling=True,
        property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
        tenure=Tenure.FREEHOLD,
        property_country=PropertyCountry.ENGLAND,
        postcode="NG1 1AA",
        lease_years_remaining=None,
        void_rate_percent=Rate(Decimal("3.85")),
        void_rate_percent_source=InputSource.CONFIG_DEFAULT,
        letting_agent_fee_percent=Rate(Decimal("10")),
        letting_agent_fee_percent_source=InputSource.CONFIG_DEFAULT,
        maintenance_reserve_percent=Rate(Decimal("1")),
        maintenance_reserve_percent_source=InputSource.CONFIG_DEFAULT,
        landlord_insurance_annual=Money(Decimal("800")),
        landlord_insurance_annual_source=InputSource.USER_OVERRIDE,
        purchase_legal_costs=Money(Decimal("1500")),
        purchase_legal_costs_source=InputSource.USER_OVERRIDE,
        refurbishment_cost=Money(Decimal("0")),
        refurbishment_cost_source=InputSource.USER_OVERRIDE,
        annual_service_charge=Money(Decimal("0")),
        annual_service_charge_source=InputSource.CONFIG_DEFAULT,
        annual_ground_rent=Money(Decimal("0")),
        annual_ground_rent_source=InputSource.CONFIG_DEFAULT,
        annual_accountancy_cost=Money(Decimal("0")),
        annual_accountancy_cost_source=InputSource.CONFIG_DEFAULT,
    )

    outputs = SnapshotOutputs(
        gross_annual_rent_gbp=Money(Decimal("11400.00")),
        effective_annual_rent_gbp=Money(Decimal("10961.10")),
        total_operating_costs_annual_gbp=Money(Decimal("4293.20")),
        net_operating_income_gbp=Money(Decimal("6667.90")),
        annual_mortgage_cost_gbp=Money(Decimal("6750.00")),
        annual_tax_liability_gbp=Money(Decimal("0.00")),
        annual_cash_flow_gbp=Money(Decimal("-331.90")),
        monthly_cash_flow_gbp=Money(Decimal("-27.66")),
        gross_yield_percent=Rate(Decimal("5.70")),
        net_yield_percent=Rate(Decimal("3.33")),
        roce_percent=Rate(Decimal("10.26")),
        cash_on_cash_return_percent=Rate(Decimal("-0.53")),
        ltv_percent=Rate(Decimal("75.00")),
        icr_percent=Rate(Decimal("98.78")),
        total_sdlt_gbp=Money(Decimal("7500.00")),
        total_acquisition_cost_gbp=Money(Decimal("209000.00")),
        total_cash_deployed_gbp=Money(Decimal("59000.00")),
    )

    intermediates = SnapshotIntermediates(
        void_rate_decimal_applied=Decimal("0.04"),
        gross_annual_rent_gbp=Money(Decimal("11400.00")),
        effective_annual_rent_gbp=Money(Decimal("10961.10")),
        loan_amount_gbp=Money(Decimal("150000.00")),
        ltv_percent=Rate(Decimal("75.00")),
        monthly_mortgage_payment_gbp=Money(Decimal("562.50")),
        annual_mortgage_cost_gbp=Money(Decimal("6750.00")),
        annual_mortgage_interest_gbp=Money(Decimal("6750.00")),
        letting_agent_annual_gbp=Money(Decimal("1368.00")),
        letting_agent_vat_rate_applied=Rate(Decimal("20")),
        annual_maintenance_reserve_gbp=Money(Decimal("2000.00")),
        total_operating_costs_annual_gbp=Money(Decimal("4293.20")),
        net_operating_income_gbp=Money(Decimal("6667.90")),
        sdlt_band_breakdown=(
            SDLTBandResult(
                band_lower=Money(Decimal("0")),
                band_upper=Money(Decimal("250000")),
                rate=Rate(Decimal("0")),
                taxable_in_band=Money(Decimal("200000")),
                tax_in_band=Money(Decimal("0")),
            ),
            SDLTBandResult(
                band_lower=Money(Decimal("0")),
                band_upper=None,
                rate=Rate(Decimal("3")),
                taxable_in_band=Money(Decimal("250000")),
                tax_in_band=Money(Decimal("7500")),
            ),
        ),
        sdlt_base_gbp=Money(Decimal("0.00")),
        sdlt_surcharge_gbp=Money(Decimal("7500.00")),
        sdlt_surcharge_rate_applied=Rate(Decimal("3")),
        total_sdlt_gbp=Money(Decimal("7500.00")),
        total_acquisition_cost_gbp=Money(Decimal("209000.00")),
        total_cash_deployed_gbp=Money(Decimal("59000.00")),
        stressed_annual_interest_gbp=Money(Decimal("8250.00")),
        stress_test_rate_applied_percent=Rate(Decimal("5.5")),
        taxable_income_or_profit_gbp=Money(Decimal("6793.10")),
        income_tax_gross_gbp=Money(Decimal("1358.62")),
        mortgage_interest_tax_credit_gbp=Money(Decimal("1425.00")),
        corporation_tax_gross_gbp=None,
        annual_tax_liability_gbp=Money(Decimal("0.00")),
        pre_tax_annual_cash_flow_gbp=Money(Decimal("-82.10")),
        section_24_applies=True,
    )

    risk_flags = [
        RiskFlag(
            code="NEGATIVE_CASHFLOW",
            severity=FlagSeverity.HIGH,
            triggered_by_field="annual_cash_flow_gbp",
            triggered_by_value="-331.90",
            message="This deal produces a negative annual cash flow.",
        ),
        RiskFlag(
            code="LOW_ICR_BASIC",
            severity=FlagSeverity.HIGH,
            triggered_by_field="icr_percent",
            triggered_by_value="98.78",
            message="ICR is below the basic-rate lender threshold of 125%.",
        ),
        RiskFlag(
            code="RENT_UNVERIFIED",
            severity=FlagSeverity.INFO,
            triggered_by_field="monthly_rent",
            triggered_by_value="950.00",
            message="Rental income has not been verified against market data.",
        ),
    ]

    validation_warnings: list[ValidationWarning] = []

    return CalculationSnapshot(
        id=sid,
        deal_id=deal_id,
        user_id=user_id,
        engine_version="1.0.0",
        config_version_refs=ConfigVersionRefs(
            assumption_config_version_id=assumption_id,
            sdlt_config_version_id=sdlt_id,
            corporation_tax_config_version_id=ct_id,
        ),
        calculated_at=datetime.now(UTC),
        inputs=inputs,
        outputs=outputs,
        intermediates=intermediates,
        risk_flags=risk_flags,
        validation_warnings=validation_warnings,
    )
