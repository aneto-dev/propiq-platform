"""
Snapshot immutability structure tests.

Verifies that the repository exposes no mutation surface beyond
mark_superseded(), and that the snapshot sub-entities are frozen
(immutable after construction) as required by the domain invariant.

Architecture:
    DOMAIN_MODEL_ARCHITECTURE.md Part 8 — snapshot immutability.
    REPOSITORY_ARCHITECTURE.md Part 5.1 — no update other than supersession.
    PERSISTENCE_ARCHITECTURE.md Part 3.
"""

from __future__ import annotations

import pytest

from app.domain.entities.snapshot import (
    CalculationSnapshot,
    ConfigVersionRefs,
    RiskFlag,
    SDLTBandResult,
    SnapshotInputs,
    SnapshotOutputs,
    ValidationWarning,
)
from app.repositories.interfaces.i_snapshot import ISnapshotRepository
from app.repositories.snapshot_repository import SnapshotRepository


class TestSnapshotSubEntityImmutability:
    """Frozen sub-entities raise FrozenInstanceError on mutation attempt."""

    def test_snapshot_inputs_is_frozen(self) -> None:
        """SnapshotInputs is frozen=True — mutation raises FrozenInstanceError."""
        from dataclasses import FrozenInstanceError
        from decimal import Decimal

        from app.domain.enums import (
            IncomeTaxBand,
            InputSource,
            MortgageType,
            OwnershipStructure,
            PropertyCountry,
            PropertyType,
            Tenure,
        )
        from app.domain.value_objects.money import Money
        from app.domain.value_objects.rate import Rate

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
        with pytest.raises(FrozenInstanceError):
            inputs.postcode = "SW1A 1AA"  # type: ignore[misc]

    def test_risk_flag_is_frozen(self) -> None:
        from dataclasses import FrozenInstanceError

        from app.domain.enums import FlagSeverity

        flag = RiskFlag(
            code="TEST",
            severity=FlagSeverity.HIGH,
            triggered_by_field="field",
            triggered_by_value="val",
            message="msg",
        )
        with pytest.raises(FrozenInstanceError):
            flag.code = "CHANGED"  # type: ignore[misc]

    def test_validation_warning_is_frozen(self) -> None:
        from dataclasses import FrozenInstanceError

        warning = ValidationWarning(
            rule_code="V-01", field="f", message="m"
        )
        with pytest.raises(FrozenInstanceError):
            warning.rule_code = "V-99"  # type: ignore[misc]

    def test_config_version_refs_is_frozen(self) -> None:
        import uuid
        from dataclasses import FrozenInstanceError

        refs = ConfigVersionRefs(
            assumption_config_version_id=uuid.uuid4(),
            sdlt_config_version_id=uuid.uuid4(),
            corporation_tax_config_version_id=uuid.uuid4(),
        )
        with pytest.raises(FrozenInstanceError):
            refs.assumption_config_version_id = uuid.uuid4()  # type: ignore[misc]

    def test_sdlt_band_result_is_frozen(self) -> None:
        from dataclasses import FrozenInstanceError
        from decimal import Decimal

        from app.domain.value_objects.money import Money
        from app.domain.value_objects.rate import Rate

        band = SDLTBandResult(
            band_lower=Money(Decimal("0")),
            band_upper=Money(Decimal("250000")),
            rate=Rate(Decimal("0")),
            taxable_in_band=Money(Decimal("200000")),
            tax_in_band=Money(Decimal("0")),
        )
        with pytest.raises(FrozenInstanceError):
            band.rate = Rate(Decimal("5"))  # type: ignore[misc]


class TestSnapshotRootMutability:
    """CalculationSnapshot root is mutable only for is_superseded/superseded_at."""

    def test_calculation_snapshot_is_superseded_is_mutable(self) -> None:
        import uuid
        from datetime import UTC, datetime
        from decimal import Decimal

        from app.domain.enums import (
            IncomeTaxBand,
            InputSource,
            MortgageType,
            OwnershipStructure,
            PropertyCountry,
            PropertyType,
            Tenure,
        )
        from app.domain.value_objects.money import Money
        from app.domain.value_objects.rate import Rate

        # Build a minimal snapshot with mocked sub-entities
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
            gross_annual_rent_gbp=Money(Decimal("11400")),
            effective_annual_rent_gbp=Money(Decimal("10961")),
            total_operating_costs_annual_gbp=Money(Decimal("4293")),
            net_operating_income_gbp=Money(Decimal("6668")),
            annual_mortgage_cost_gbp=Money(Decimal("6750")),
            annual_tax_liability_gbp=Money(Decimal("0")),
            annual_cash_flow_gbp=Money(Decimal("-332")),
            monthly_cash_flow_gbp=Money(Decimal("-27")),
            gross_yield_percent=Rate(Decimal("5.70")),
            net_yield_percent=Rate(Decimal("3.33")),
            roce_percent=Rate(Decimal("10.26")),
            cash_on_cash_return_percent=Rate(Decimal("-0.53")),
            ltv_percent=Rate(Decimal("75")),
            icr_percent=Rate(Decimal("98.78")),
            total_sdlt_gbp=Money(Decimal("7500")),
            total_acquisition_cost_gbp=Money(Decimal("209000")),
            total_cash_deployed_gbp=Money(Decimal("59000")),
        )

        sid = uuid.uuid4()
        snap = CalculationSnapshot(
            id=sid,
            deal_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            engine_version="1.0.0",
            config_version_refs=ConfigVersionRefs(
                assumption_config_version_id=uuid.uuid4(),
                sdlt_config_version_id=uuid.uuid4(),
                corporation_tax_config_version_id=uuid.uuid4(),
            ),
            calculated_at=datetime.now(UTC),
            inputs=inputs,
            outputs=outputs,
            intermediates=None,  # type: ignore[arg-type]
            risk_flags=[],
            validation_warnings=[],
        )
        # The only permitted mutation
        snap.is_superseded = True
        assert snap.is_superseded is True


class TestRepositoryImmutabilityInterface:
    def test_interface_has_no_update_or_delete(self) -> None:
        """No update methods exist for any field other than supersession."""
        assert not hasattr(ISnapshotRepository, "update")
        assert not hasattr(ISnapshotRepository, "delete")
        assert hasattr(ISnapshotRepository, "mark_superseded")

    def test_implementation_has_no_update_or_delete(self) -> None:
        assert not hasattr(SnapshotRepository, "update")
        assert not hasattr(SnapshotRepository, "delete")
