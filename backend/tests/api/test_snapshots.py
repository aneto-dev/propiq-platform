"""
Snapshot read API route tests.

Covers:
    GET /api/v1/snapshots/{snapshot_id}        — get_snapshot (display level)
    GET /api/v1/snapshots/{snapshot_id}/full   — get_full_snapshot (with intermediates)
    GET /api/v1/snapshots/?deal_id={id}        — list_snapshot_history

All tests use the mock-authenticated client from conftest.py.
SnapshotService is replaced with AsyncMock — no DB required.

Architecture:
    IMPLEMENTATION_ROADMAP.md Commit 6.5.
    APPLICATION_SERVICE_ARCHITECTURE.md Part 6.2.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_snapshot_service
from app.domain.entities.snapshot import (
    CalculationSnapshot,
    ConfigVersionRefs,
    SDLTBandResult,
    SnapshotInputs,
    SnapshotIntermediates,
    SnapshotOutputs,
)
from app.domain.entities.user import User
from app.domain.enums import (
    IncomeTaxBand,
    InputSource,
    MortgageType,
    OwnershipStructure,
    PropertyCountry,
    PropertyType,
    Tenure,
)
from app.domain.errors import NotFoundError
from app.domain.value_objects.money import Money
from app.domain.value_objects.rate import Rate
from app.main import create_app
from app.repositories.interfaces.i_snapshot import SnapshotHistoryEntry, SnapshotSummary

# ---------------------------------------------------------------------------
# Test data constants
# ---------------------------------------------------------------------------

_SNAP_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
_DEAL_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _m(amount: str) -> Money:
    return Money(Decimal(amount))


def _r(value: str) -> Rate:
    return Rate(Decimal(value))


def _make_outputs() -> SnapshotOutputs:
    return SnapshotOutputs(
        gross_annual_rent_gbp=_m("11400.00"),
        effective_annual_rent_gbp=_m("10989.00"),
        total_operating_costs_annual_gbp=_m("3576.70"),
        net_operating_income_gbp=_m("7412.30"),
        annual_mortgage_cost_gbp=_m("7125.00"),
        annual_tax_liability_gbp=_m("0.00"),
        annual_cash_flow_gbp=_m("-331.90"),
        monthly_cash_flow_gbp=_m("-27.66"),
        gross_yield_percent=_r("5.70"),
        net_yield_percent=_r("3.71"),
        roce_percent=_r("-0.66"),
        cash_on_cash_return_percent=_r("-0.66"),
        ltv_percent=_r("75.00"),
        icr_percent=_r("104.04"),
        total_sdlt_gbp=_m("7500.00"),
        total_acquisition_cost_gbp=_m("209500.00"),
        total_cash_deployed_gbp=_m("59500.00"),
    )


def _make_intermediates() -> SnapshotIntermediates:
    return SnapshotIntermediates(
        void_rate_decimal_applied=Decimal("0.036000"),
        gross_annual_rent_gbp=_m("11400.00"),
        effective_annual_rent_gbp=_m("10989.00"),
        loan_amount_gbp=_m("150000.00"),
        ltv_percent=_r("75.00"),
        monthly_mortgage_payment_gbp=_m("593.75"),
        annual_mortgage_cost_gbp=_m("7125.00"),
        annual_mortgage_interest_gbp=_m("7125.00"),
        letting_agent_annual_gbp=_m("1318.68"),
        letting_agent_vat_rate_applied=_r("20.00"),
        annual_maintenance_reserve_gbp=_m("600.00"),
        total_operating_costs_annual_gbp=_m("3576.70"),
        net_operating_income_gbp=_m("7412.30"),
        sdlt_band_breakdown=(
            SDLTBandResult(
                band_lower=_m("0.00"),
                band_upper=_m("250000.00"),
                rate=_r("5.00"),
                taxable_in_band=_m("200000.00"),
                tax_in_band=_m("10000.00"),
            ),
        ),
        sdlt_base_gbp=_m("1500.00"),
        sdlt_surcharge_gbp=_m("6000.00"),
        sdlt_surcharge_rate_applied=_r("3.00"),
        total_sdlt_gbp=_m("7500.00"),
        total_acquisition_cost_gbp=_m("209500.00"),
        total_cash_deployed_gbp=_m("59500.00"),
        stressed_annual_interest_gbp=_m("8500.00"),
        stress_test_rate_applied_percent=_r("5.50"),
        taxable_income_or_profit_gbp=_m("3864.30"),
        income_tax_gross_gbp=_m("1358.62"),
        mortgage_interest_tax_credit_gbp=_m("1425.00"),
        corporation_tax_gross_gbp=None,
        annual_tax_liability_gbp=_m("0.00"),
        pre_tax_annual_cash_flow_gbp=_m("-331.90"),
        section_24_applies=True,
    )


def _make_snapshot_summary() -> SnapshotSummary:
    return SnapshotSummary(
        id=_SNAP_ID,
        deal_id=_DEAL_ID,
        engine_version="1.0.0",
        calculated_at=_NOW,
        is_superseded=False,
        outputs=_make_outputs(),
        risk_flags=[],
        validation_warnings=[],
        config_version_refs=ConfigVersionRefs(
            sdlt_config_version_id=uuid.uuid4(),
            corporation_tax_config_version_id=uuid.uuid4(),
            assumption_config_version_id=uuid.uuid4(),
        ),
    )


def _make_full_snapshot() -> CalculationSnapshot:
    return CalculationSnapshot(
        id=_SNAP_ID,
        deal_id=_DEAL_ID,
        user_id=_USER_ID,
        engine_version="1.0.0",
        config_version_refs=ConfigVersionRefs(
            sdlt_config_version_id=uuid.uuid4(),
            corporation_tax_config_version_id=uuid.uuid4(),
            assumption_config_version_id=uuid.uuid4(),
        ),
        calculated_at=_NOW,
        inputs=SnapshotInputs(
            purchase_price=_m("200000.00"),
            monthly_rent=_m("950.00"),
            deposit_amount=_m("50000.00"),
            mortgage_interest_rate=_r("4.75"),
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
            void_rate_percent=_r("3.60"),
            void_rate_percent_source=InputSource.CONFIG_DEFAULT,
            letting_agent_fee_percent=_r("10.00"),
            letting_agent_fee_percent_source=InputSource.CONFIG_DEFAULT,
            maintenance_reserve_percent=_r("0.50"),
            maintenance_reserve_percent_source=InputSource.CONFIG_DEFAULT,
            landlord_insurance_annual=_m("300.00"),
            landlord_insurance_annual_source=InputSource.CONFIG_DEFAULT,
            purchase_legal_costs=_m("1500.00"),
            purchase_legal_costs_source=InputSource.CONFIG_DEFAULT,
            refurbishment_cost=_m("0.00"),
            refurbishment_cost_source=InputSource.CONFIG_DEFAULT,
            annual_service_charge=_m("0.00"),
            annual_service_charge_source=InputSource.CONFIG_DEFAULT,
            annual_ground_rent=_m("0.00"),
            annual_ground_rent_source=InputSource.CONFIG_DEFAULT,
            annual_accountancy_cost=_m("200.00"),
            annual_accountancy_cost_source=InputSource.CONFIG_DEFAULT,
        ),
        outputs=_make_outputs(),
        intermediates=_make_intermediates(),
        risk_flags=[],
        validation_warnings=[],
    )


def _make_history_entry(snap_id: uuid.UUID = _SNAP_ID) -> SnapshotHistoryEntry:
    return SnapshotHistoryEntry(
        id=snap_id,
        deal_id=_DEAL_ID,
        engine_version="1.0.0",
        calculated_at=_NOW,
        is_superseded=False,
        risk_flag_count_high=0,
        risk_flag_count_medium=0,
        risk_flag_count_info=0,
        annual_cash_flow_gbp=Decimal("-331.90"),
        gross_yield_percent=Decimal("5.70"),
    )


def _make_client(mock_svc: object, mock_user: User) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_snapshot_service] = lambda: mock_svc
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /api/v1/snapshots/{snapshot_id}
# ---------------------------------------------------------------------------


class TestGetSnapshot:
    def test_returns_200_with_display_summary(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.get_display_summary = AsyncMock(return_value=_make_snapshot_summary())

        with _make_client(svc, mock_user) as client:
            response = client.get(f"/api/v1/snapshots/{_SNAP_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(_SNAP_ID)
        assert data["deal_id"] == str(_DEAL_ID)
        assert data["engine_version"] == "1.0.0"
        assert data["is_superseded"] is False
        assert data["outputs"]["annual_cash_flow_gbp"] == "-331.90"
        assert data["outputs"]["monthly_cash_flow_gbp"] == "-27.66"
        assert "intermediates" not in data

    def test_non_owned_snapshot_returns_404(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.get_display_summary = AsyncMock(
            side_effect=NotFoundError(entity="snapshot", id=_SNAP_ID)
        )

        with _make_client(svc, mock_user) as client:
            response = client.get(f"/api/v1/snapshots/{_SNAP_ID}")

        assert response.status_code == 404

    def test_response_excludes_intermediates(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.get_display_summary = AsyncMock(return_value=_make_snapshot_summary())

        with _make_client(svc, mock_user) as client:
            response = client.get(f"/api/v1/snapshots/{_SNAP_ID}")

        assert response.status_code == 200
        assert "intermediates" not in response.json()


# ---------------------------------------------------------------------------
# GET /api/v1/snapshots/{snapshot_id}/full
# ---------------------------------------------------------------------------


class TestGetFullSnapshot:
    def test_returns_200_with_intermediates(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.get_full_snapshot = AsyncMock(return_value=_make_full_snapshot())

        with _make_client(svc, mock_user) as client:
            response = client.get(f"/api/v1/snapshots/{_SNAP_ID}/full")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(_SNAP_ID)
        assert "intermediates" in data

    def test_sdlt_band_breakdown_is_ordered_array(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.get_full_snapshot = AsyncMock(return_value=_make_full_snapshot())

        with _make_client(svc, mock_user) as client:
            response = client.get(f"/api/v1/snapshots/{_SNAP_ID}/full")

        assert response.status_code == 200
        intermediates = response.json()["intermediates"]
        assert "sdlt_band_breakdown" in intermediates
        bands = intermediates["sdlt_band_breakdown"]
        assert isinstance(bands, list)
        assert len(bands) == 1
        assert bands[0]["band_lower"] == "0.00"
        assert bands[0]["tax_in_band"] == "10000.00"

    def test_non_owned_snapshot_returns_404(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.get_full_snapshot = AsyncMock(
            side_effect=NotFoundError(entity="snapshot", id=_SNAP_ID)
        )

        with _make_client(svc, mock_user) as client:
            response = client.get(f"/api/v1/snapshots/{_SNAP_ID}/full")

        assert response.status_code == 404

    def test_individual_tax_fields_present_nullable(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.get_full_snapshot = AsyncMock(return_value=_make_full_snapshot())

        with _make_client(svc, mock_user) as client:
            response = client.get(f"/api/v1/snapshots/{_SNAP_ID}/full")

        assert response.status_code == 200
        intermediates = response.json()["intermediates"]
        assert intermediates["income_tax_gross_gbp"] == "1358.62"
        assert intermediates["corporation_tax_gross_gbp"] is None
        assert intermediates["section_24_applies"] is True


# ---------------------------------------------------------------------------
# GET /api/v1/snapshots/?deal_id={id}
# ---------------------------------------------------------------------------


class TestListSnapshotHistory:
    def test_returns_200_with_entries_ordered_desc(self, mock_user: User) -> None:
        snap_id_1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
        snap_id_2 = uuid.UUID("22222222-2222-2222-2222-222222222222")
        entries = [
            _make_history_entry(snap_id_1),
            _make_history_entry(snap_id_2),
        ]
        svc = MagicMock()
        svc.get_history_for_deal = AsyncMock(return_value=entries)

        with _make_client(svc, mock_user) as client:
            response = client.get(f"/api/v1/snapshots/?deal_id={_DEAL_ID}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == str(snap_id_1)
        assert data[0]["annual_cash_flow_gbp"] == "-331.90"
        assert data[0]["gross_yield_percent"] == "5.70"

    def test_returns_empty_list_for_deal_with_no_snapshots(
        self, mock_user: User
    ) -> None:
        svc = MagicMock()
        svc.get_history_for_deal = AsyncMock(return_value=[])

        with _make_client(svc, mock_user) as client:
            response = client.get(f"/api/v1/snapshots/?deal_id={_DEAL_ID}")

        assert response.status_code == 200
        assert response.json() == []

    def test_non_owned_deal_returns_404(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.get_history_for_deal = AsyncMock(
            side_effect=NotFoundError(entity="deal", id=_DEAL_ID)
        )

        with _make_client(svc, mock_user) as client:
            response = client.get(f"/api/v1/snapshots/?deal_id={_DEAL_ID}")

        assert response.status_code == 404

    def test_missing_deal_id_returns_422(self, mock_user: User) -> None:
        svc = MagicMock()

        with _make_client(svc, mock_user) as client:
            response = client.get("/api/v1/snapshots/")

        assert response.status_code == 422
