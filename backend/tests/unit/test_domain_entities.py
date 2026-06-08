"""
Unit tests for domain entity invariants.

Tests behaviour methods and structural invariants enforced on domain
entities. No infrastructure dependencies — no database, no FastAPI,
no ORM. All tests must pass with Docker stopped.

Covers:
    Deal                    — status transitions, archive guard
    DealWorkingInputs       — nullable default state
    CalculationSnapshot     — frozen sub-entities, mutable root fields
    SnapshotOutputs         — frozen immutability
    SnapshotInputs          — frozen immutability
"""

import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.entities.deal import Deal, DealWorkingInputs
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
)
from app.domain.errors import DomainError
from app.domain.value_objects.money import Money
from app.domain.value_objects.rate import Rate

# ---------------------------------------------------------------------------
# Helpers — minimal valid instances for use across tests
# ---------------------------------------------------------------------------


def _make_deal(status: DealStatus = DealStatus.DRAFT) -> Deal:
    """Return a minimal valid Deal with the given status."""
    return Deal(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        property_id=uuid.uuid4(),
        label="Test deal",
        status=status,
    )


def _make_snapshot_outputs() -> SnapshotOutputs:
    """Return a minimal valid SnapshotOutputs for mutation tests."""
    D = Decimal
    return SnapshotOutputs(
        gross_annual_rent_gbp=Money(D("12000")),
        effective_annual_rent_gbp=Money(D("11538")),
        total_operating_costs_annual_gbp=Money(D("5000")),
        net_operating_income_gbp=Money(D("6538")),
        annual_mortgage_cost_gbp=Money(D("7125")),
        annual_tax_liability_gbp=Money(D("0")),
        annual_cash_flow_gbp=Money(D("-331.90")),
        monthly_cash_flow_gbp=Money(D("-27.66")),
        gross_yield_percent=Rate(D("6.00")),
        net_yield_percent=Rate(D("3.24")),
        roce_percent=Rate(D("12.97")),
        cash_on_cash_return_percent=Rate(D("-0.66")),
        ltv_percent=Rate(D("75.00")),
        icr_percent=Rate(D("161.66")),
        total_sdlt_gbp=Money(D("7500")),
        total_acquisition_cost_gbp=Money(D("210000")),
        total_cash_deployed_gbp=Money(D("60000")),
    )


def _make_snapshot_inputs() -> SnapshotInputs:
    """Return a minimal valid SnapshotInputs for mutation tests."""
    D = Decimal
    return SnapshotInputs(
        purchase_price=Money(D("200000")),
        monthly_rent=Money(D("1000")),
        deposit_amount=Money(D("50000")),
        mortgage_interest_rate=Rate(D("4.75")),
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
        void_rate_percent=Rate(D("3.85")),
        void_rate_percent_source=InputSource.CONFIG_DEFAULT,
        letting_agent_fee_percent=Rate(D("10")),
        letting_agent_fee_percent_source=InputSource.CONFIG_DEFAULT,
        maintenance_reserve_percent=Rate(D("1")),
        maintenance_reserve_percent_source=InputSource.CONFIG_DEFAULT,
        landlord_insurance_annual=Money(D("800")),
        landlord_insurance_annual_source=InputSource.CONFIG_DEFAULT,
        purchase_legal_costs=Money(D("2500")),
        purchase_legal_costs_source=InputSource.CONFIG_DEFAULT,
        refurbishment_cost=Money(D("0")),
        refurbishment_cost_source=InputSource.USER_OVERRIDE,
        annual_service_charge=Money(D("0")),
        annual_service_charge_source=InputSource.CONFIG_DEFAULT,
        annual_ground_rent=Money(D("0")),
        annual_ground_rent_source=InputSource.CONFIG_DEFAULT,
        annual_accountancy_cost=Money(D("0")),
        annual_accountancy_cost_source=InputSource.CONFIG_DEFAULT,
    )


def _make_snapshot_intermediates() -> SnapshotIntermediates:
    """Return a minimal valid SnapshotIntermediates for tests."""
    D = Decimal
    band = SDLTBandResult(
        band_lower=Money(D("0")),
        band_upper=Money(D("125000")),
        rate=Rate(D("0")),
        taxable_in_band=Money(D("125000")),
        tax_in_band=Money(D("0")),
    )
    return SnapshotIntermediates(
        void_rate_decimal_applied=D("0.0384615"),
        gross_annual_rent_gbp=Money(D("12000")),
        effective_annual_rent_gbp=Money(D("11538.46")),
        loan_amount_gbp=Money(D("150000")),
        ltv_percent=Rate(D("75")),
        monthly_mortgage_payment_gbp=Money(D("593.75")),
        annual_mortgage_cost_gbp=Money(D("7125")),
        annual_mortgage_interest_gbp=Money(D("7125")),
        letting_agent_annual_gbp=Money(D("1384.62")),
        letting_agent_vat_rate_applied=Rate(D("20")),
        annual_maintenance_reserve_gbp=Money(D("2000")),
        total_operating_costs_annual_gbp=Money(D("5053.80")),
        net_operating_income_gbp=Money(D("6484.20")),
        sdlt_band_breakdown=(band,),
        sdlt_base_gbp=Money(D("1500")),
        sdlt_surcharge_gbp=Money(D("6000")),
        sdlt_surcharge_rate_applied=Rate(D("3")),
        total_sdlt_gbp=Money(D("7500")),
        total_acquisition_cost_gbp=Money(D("210000")),
        total_cash_deployed_gbp=Money(D("60000")),
        stressed_annual_interest_gbp=Money(D("8250")),
        stress_test_rate_applied_percent=Rate(D("5.5")),
        taxable_income_or_profit_gbp=Money(D("6484.20")),
        income_tax_gross_gbp=Money(D("1296.84")),
        mortgage_interest_tax_credit_gbp=Money(D("1425")),
        corporation_tax_gross_gbp=None,
        annual_tax_liability_gbp=Money(D("0")),
        pre_tax_annual_cash_flow_gbp=Money(D("-331.90")),
        section_24_applies=True,
    )


def _make_calculation_snapshot() -> CalculationSnapshot:
    """Return a minimal valid CalculationSnapshot for tests."""
    return CalculationSnapshot(
        id=uuid.uuid4(),
        deal_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        engine_version="1.0.0",
        config_version_refs=ConfigVersionRefs(
            assumption_config_version_id=uuid.uuid4(),
            sdlt_config_version_id=uuid.uuid4(),
            corporation_tax_config_version_id=uuid.uuid4(),
        ),
        calculated_at=datetime.now(UTC),
        inputs=_make_snapshot_inputs(),
        outputs=_make_snapshot_outputs(),
        intermediates=_make_snapshot_intermediates(),
        risk_flags=[],
        validation_warnings=[],
    )


# ---------------------------------------------------------------------------
# Deal — behaviour methods
# ---------------------------------------------------------------------------


class TestDealArchive:
    """Tests for Deal.archive() status transition."""

    def test_archive_already_archived_deal_raises_domain_error(self) -> None:
        """
        Calling archive() on an ARCHIVED deal must raise DomainError.

        This is the roadmap-specified test (Commit 1.6 spec).
        Enforces DOMAIN_MODEL_ARCHITECTURE.md Part 9.3.
        """
        deal = _make_deal(DealStatus.ARCHIVED)
        with pytest.raises(DomainError) as exc_info:
            deal.archive()
        assert "already archived" in exc_info.value.message.lower()

    def test_archive_draft_deal_succeeds(self) -> None:
        """A DRAFT deal can be archived (user abandons a draft)."""
        deal = _make_deal(DealStatus.DRAFT)
        deal.archive()
        assert deal.status == DealStatus.ARCHIVED

    def test_archive_analysed_deal_succeeds(self) -> None:
        """An ANALYSED deal can be archived."""
        deal = _make_deal(DealStatus.ANALYSED)
        deal.archive()
        assert deal.status == DealStatus.ARCHIVED

    def test_archive_sets_updated_at(self) -> None:
        """archive() sets updated_at to a UTC-aware datetime."""
        deal = _make_deal(DealStatus.DRAFT)
        assert deal.updated_at is None
        deal.archive()
        assert deal.updated_at is not None
        assert deal.updated_at.tzinfo is not None


class TestDealAdvanceStatus:
    """Tests for Deal.advance_status() pipeline progression."""

    def test_analysed_advances_to_offer_submitted(self) -> None:
        deal = _make_deal(DealStatus.ANALYSED)
        deal.advance_status()
        assert deal.status == DealStatus.OFFER_SUBMITTED

    def test_offer_submitted_advances_to_purchased(self) -> None:
        deal = _make_deal(DealStatus.OFFER_SUBMITTED)
        deal.advance_status()
        assert deal.status == DealStatus.PURCHASED

    def test_purchased_advances_to_held(self) -> None:
        deal = _make_deal(DealStatus.PURCHASED)
        deal.advance_status()
        assert deal.status == DealStatus.HELD

    def test_held_advances_to_exited(self) -> None:
        deal = _make_deal(DealStatus.HELD)
        deal.advance_status()
        assert deal.status == DealStatus.EXITED

    def test_draft_cannot_advance(self) -> None:
        deal = _make_deal(DealStatus.DRAFT)
        with pytest.raises(DomainError):
            deal.advance_status()

    def test_exited_cannot_advance(self) -> None:
        deal = _make_deal(DealStatus.EXITED)
        with pytest.raises(DomainError):
            deal.advance_status()

    def test_archived_cannot_advance(self) -> None:
        deal = _make_deal(DealStatus.ARCHIVED)
        with pytest.raises(DomainError):
            deal.advance_status()

    def test_advance_sets_updated_at(self) -> None:
        deal = _make_deal(DealStatus.ANALYSED)
        assert deal.updated_at is None
        deal.advance_status()
        assert deal.updated_at is not None
        assert deal.updated_at.tzinfo is not None

    def test_full_pipeline_progression(self) -> None:
        """A deal can walk through the entire lifecycle in sequence."""
        deal = _make_deal(DealStatus.ANALYSED)
        deal.advance_status()
        assert deal.status == DealStatus.OFFER_SUBMITTED
        deal.advance_status()
        assert deal.status == DealStatus.PURCHASED
        deal.advance_status()
        assert deal.status == DealStatus.HELD
        deal.advance_status()
        assert deal.status == DealStatus.EXITED


class TestDealApplySnapshotCreated:
    """Tests for Deal.apply_snapshot_created() status transitions."""

    def test_draft_transitions_to_analysed(self) -> None:
        """
        First snapshot on a DRAFT deal transitions status to ANALYSED.

        This is the roadmap-specified test (Commit 1.6 spec).
        Enforces DOMAIN_MODEL_ARCHITECTURE.md Part 4.4.
        """
        deal = _make_deal(DealStatus.DRAFT)
        snapshot_id = uuid.uuid4()
        deal.apply_snapshot_created(snapshot_id)
        assert deal.status == DealStatus.ANALYSED

    def test_analysed_stays_analysed_on_recalculation(self) -> None:
        """
        Recalculation on an ANALYSED deal keeps status as ANALYSED.

        This is the roadmap-specified test (Commit 1.6 spec).
        """
        deal = _make_deal(DealStatus.ANALYSED)
        deal.apply_snapshot_created(uuid.uuid4())
        assert deal.status == DealStatus.ANALYSED

    def test_snapshot_pointer_updated_on_first_calculation(self) -> None:
        """latest_snapshot_id is set to the new snapshot UUID."""
        deal = _make_deal(DealStatus.DRAFT)
        snap_id = uuid.uuid4()
        deal.apply_snapshot_created(snap_id)
        assert deal.latest_snapshot_id == snap_id

    def test_snapshot_pointer_updated_on_recalculation(self) -> None:
        """latest_snapshot_id is updated to the newer snapshot on recalc."""
        deal = _make_deal(DealStatus.ANALYSED)
        first_snap = uuid.uuid4()
        second_snap = uuid.uuid4()
        deal.apply_snapshot_created(first_snap)
        deal.apply_snapshot_created(second_snap)
        assert deal.latest_snapshot_id == second_snap

    def test_apply_snapshot_sets_updated_at(self) -> None:
        """apply_snapshot_created() sets updated_at to a UTC-aware datetime."""
        deal = _make_deal(DealStatus.DRAFT)
        deal.apply_snapshot_created(uuid.uuid4())
        assert deal.updated_at is not None
        assert deal.updated_at.tzinfo is not None


# ---------------------------------------------------------------------------
# DealWorkingInputs
# ---------------------------------------------------------------------------


class TestDealWorkingInputs:
    """Tests for DealWorkingInputs default state."""

    def test_all_fields_default_to_none(self) -> None:
        """
        A freshly created DealWorkingInputs has all fields as None.

        Working inputs are nullable because DRAFT deals may be incomplete.
        Completeness is enforced by the engine, not the domain entity.
        """
        inputs = DealWorkingInputs()
        nullable_fields = [
            "purchase_price", "monthly_rent", "deposit_amount",
            "mortgage_interest_rate", "mortgage_term_years",
            "mortgage_type", "ownership_structure", "income_tax_band",
            "is_additional_dwelling", "void_rate_percent",
            "letting_agent_fee_percent", "maintenance_reserve_percent",
            "landlord_insurance_annual", "purchase_legal_costs",
            "refurbishment_cost", "annual_service_charge",
            "annual_ground_rent", "annual_accountancy_cost",
        ]
        for field_name in nullable_fields:
            assert getattr(inputs, field_name) is None, (
                f"Expected {field_name} to default to None"
            )

    def test_field_count_matches_schema(self) -> None:
        """DealWorkingInputs has exactly 18 working input fields."""
        inputs = DealWorkingInputs()
        # 9 required + 9 optional — all nullable in the working inputs
        assert len(inputs.__dataclass_fields__) == 18


# ---------------------------------------------------------------------------
# SnapshotOutputs — frozen immutability
# ---------------------------------------------------------------------------


class TestSnapshotOutputsFrozen:
    """Tests for SnapshotOutputs frozen=True enforcement."""

    def test_mutation_raises_frozen_instance_error(self) -> None:
        """
        SnapshotOutputs is frozen=True. Any field mutation must raise.

        Enforces DOMAIN_MODEL_ARCHITECTURE.md invariant I-01:
        "Once a CalculationSnapshot is created... its outputs never change."
        """
        outputs = _make_snapshot_outputs()
        with pytest.raises(FrozenInstanceError):
            outputs.gross_annual_rent_gbp = Money(  # type: ignore[misc]
                Decimal("99999")
            )

    def test_negative_cash_flow_stored_correctly(self) -> None:
        """
        Negative cash flow values are valid in SnapshotOutputs.

        E-01 reference scenario: annual_cash_flow_gbp = -331.90.
        """
        outputs = _make_snapshot_outputs()
        assert outputs.annual_cash_flow_gbp.amount == Decimal("-331.90")

    def test_negative_rate_stored_correctly(self) -> None:
        """
        Negative Rate values are valid for return metrics in SnapshotOutputs.

        Architecture correction: cash_on_cash_return_percent may be negative.
        """
        outputs = _make_snapshot_outputs()
        assert outputs.cash_on_cash_return_percent.value == Decimal("-0.66")


# ---------------------------------------------------------------------------
# SnapshotInputs — frozen immutability
# ---------------------------------------------------------------------------


class TestSnapshotInputsFrozen:
    """Tests for SnapshotInputs frozen=True enforcement."""

    def test_mutation_raises_frozen_instance_error(self) -> None:
        """
        SnapshotInputs is frozen=True. Any field mutation must raise.

        Enforces DOMAIN_MODEL_ARCHITECTURE.md invariant I-01 and
        database schema invariant: snapshot_inputs is STRICTLY IMMUTABLE.
        """
        inputs = _make_snapshot_inputs()
        with pytest.raises(FrozenInstanceError):
            inputs.purchase_price = Money(Decimal("999"))  # type: ignore[misc]

    def test_source_provenance_fields_present(self) -> None:
        """
        Every optional input has a paired _source field.

        Enforces ADR-009 (assumption provenance) and the database schema
        requirement that _source columns are REQUIRED and non-nullable.
        """
        inputs = _make_snapshot_inputs()
        optional_fields = [
            "void_rate_percent", "letting_agent_fee_percent",
            "maintenance_reserve_percent", "landlord_insurance_annual",
            "purchase_legal_costs", "refurbishment_cost",
            "annual_service_charge", "annual_ground_rent",
            "annual_accountancy_cost",
        ]
        for field in optional_fields:
            source_field = f"{field}_source"
            assert hasattr(inputs, source_field), (
                f"Missing provenance field: {source_field}"
            )
            source_value = getattr(inputs, source_field)
            assert source_value is not None, (
                f"Source provenance must never be None: {source_field}"
            )


# ---------------------------------------------------------------------------
# CalculationSnapshot — mutable root, frozen sub-entities
# ---------------------------------------------------------------------------


class TestCalculationSnapshotMutability:
    """
    Tests for CalculationSnapshot mutable vs immutable field boundary.

    The root is a regular dataclass. Sub-entities are frozen=True.
    Only is_superseded and superseded_at may be mutated on the root.
    """

    def test_is_superseded_defaults_to_false(self) -> None:
        """A new snapshot is not superseded."""
        snap = _make_calculation_snapshot()
        assert snap.is_superseded is False
        assert snap.superseded_at is None

    def test_supersession_fields_are_mutable(self) -> None:
        """
        is_superseded and superseded_at can be mutated on the snapshot root.

        These are the only two permitted mutations on any snapshot field,
        enforced by column-level DB privilege grant in production.
        """
        snap = _make_calculation_snapshot()
        now = datetime.now(UTC)
        snap.is_superseded = True
        snap.superseded_at = now
        assert snap.is_superseded is True
        assert snap.superseded_at == now

    def test_risk_flags_list_present(self) -> None:
        """risk_flags is a list that may be empty."""
        snap = _make_calculation_snapshot()
        assert isinstance(snap.risk_flags, list)

    def test_validation_warnings_list_present(self) -> None:
        """validation_warnings is a list that may be empty."""
        snap = _make_calculation_snapshot()
        assert isinstance(snap.validation_warnings, list)

    def test_risk_flag_construction(self) -> None:
        """RiskFlag is frozen=True and stores all required fields."""
        flag = RiskFlag(
            code="NEGATIVE_CASHFLOW",
            severity=FlagSeverity.HIGH,
            triggered_by_field="annual_cash_flow_gbp",
            triggered_by_value="-331.90",
            message="This deal produces negative cash flow.",
        )
        assert flag.code == "NEGATIVE_CASHFLOW"
        assert flag.severity == FlagSeverity.HIGH
        with pytest.raises(FrozenInstanceError):
            flag.code = "OTHER"  # type: ignore[misc]

    def test_validation_warning_construction(self) -> None:
        """ValidationWarning is frozen=True and stores all required fields."""
        warning = ValidationWarning(
            rule_code="V-25",
            field="refurbishment_cost",
            message="No refurbishment cost entered.",
        )
        assert warning.rule_code == "V-25"
        with pytest.raises(FrozenInstanceError):
            warning.rule_code = "V-99"  # type: ignore[misc]

    def test_config_version_refs_frozen(self) -> None:
        """ConfigVersionRefs is frozen=True."""
        cvr = ConfigVersionRefs(
            assumption_config_version_id=uuid.uuid4(),
            sdlt_config_version_id=uuid.uuid4(),
            corporation_tax_config_version_id=uuid.uuid4(),
        )
        with pytest.raises(FrozenInstanceError):
            cvr.sdlt_config_version_id = uuid.uuid4()  # type: ignore[misc]
