"""
Calculation API route tests.

Covers:
    POST /api/v1/calculations/                   — run_calculation
    POST /api/v1/calculations/recalculate        — recalculate_with_current_assumptions
    POST /api/v1/calculations/reproduce-original — reproduce_original

All tests use the mock-authenticated client from conftest.py.
CalculationService is replaced with AsyncMock — no DB required.

Architecture:
    IMPLEMENTATION_ROADMAP.md Commit 6.4.
    APPLICATION_SERVICE_ARCHITECTURE.md Part 5.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api.dependencies import get_calculation_service, get_current_user
from app.domain.entities.snapshot import (
    ConfigVersionRefs,
    SnapshotOutputs,
)
from app.domain.entities.user import User
from app.domain.enums import (
    DealStatus,
)
from app.domain.errors import NotFoundError
from app.domain.value_objects.money import Money
from app.domain.value_objects.rate import Rate
from app.main import create_app
from app.repositories.interfaces.i_snapshot import SnapshotSummary
from app.services.calculation_service import (
    CalculationError as SvcCalculationError,
)
from app.services.calculation_service import CalculationSuccess
from app.services.calculation_service import (
    CalculationValidationFailure as SvcCalculationValidationFailure,
)

# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

_DEAL_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
_SNAP_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

_CALC_BODY = {
    "deal_id": str(_DEAL_ID),
    "purchase_price": "200000.00",
    "monthly_rent": "950.00",
    "deposit_amount": "50000.00",
    "mortgage_interest_rate": "4.75",
    "mortgage_term_years": 25,
    "mortgage_type": "INTEREST_ONLY",
    "ownership_structure": "INDIVIDUAL",
    "income_tax_band": "BASIC_RATE",
    "is_additional_dwelling": True,
    "property_type": "RESIDENTIAL_SINGLE_LET",
    "tenure": "FREEHOLD",
    "property_country": "ENGLAND",
    "postcode": "NG1 1AA",
}


def _make_money(amount: str) -> Money:
    return Money(Decimal(amount))


def _make_rate(value: str) -> Rate:
    return Rate(Decimal(value))


def _make_snapshot_summary() -> SnapshotSummary:
    return SnapshotSummary(
        id=_SNAP_ID,
        deal_id=_DEAL_ID,
        engine_version="1.0.0",
        calculated_at=_NOW,
        is_superseded=False,
        outputs=SnapshotOutputs(
            gross_annual_rent_gbp=_make_money("11400.00"),
            effective_annual_rent_gbp=_make_money("10989.00"),
            total_operating_costs_annual_gbp=_make_money("3576.70"),
            net_operating_income_gbp=_make_money("7412.30"),
            annual_mortgage_cost_gbp=_make_money("7125.00"),
            annual_tax_liability_gbp=_make_money("0.00"),
            annual_cash_flow_gbp=_make_money("-331.90"),
            monthly_cash_flow_gbp=_make_money("-27.66"),
            gross_yield_percent=_make_rate("5.70"),
            net_yield_percent=_make_rate("3.71"),
            roce_percent=_make_rate("-0.66"),
            cash_on_cash_return_percent=_make_rate("-0.66"),
            ltv_percent=_make_rate("75.00"),
            icr_percent=_make_rate("104.04"),
            total_sdlt_gbp=_make_money("7500.00"),
            total_acquisition_cost_gbp=_make_money("209500.00"),
            total_cash_deployed_gbp=_make_money("59500.00"),
        ),
        risk_flags=[],
        validation_warnings=[],
        config_version_refs=ConfigVersionRefs(
            sdlt_config_version_id=uuid.uuid4(),
            corporation_tax_config_version_id=uuid.uuid4(),
            assumption_config_version_id=uuid.uuid4(),
        ),
    )


def _make_success() -> CalculationSuccess:
    return CalculationSuccess(
        snapshot_id=_SNAP_ID,
        snapshot_summary=_make_snapshot_summary(),
        deal_status_after=DealStatus.ANALYSED,
    )


def _make_client(mock_svc: object, mock_user: User) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_calculation_service] = lambda: mock_svc
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /api/v1/calculations/
# ---------------------------------------------------------------------------


class TestRunCalculation:
    def test_returns_201_with_snapshot_summary(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.run_calculation = AsyncMock(return_value=_make_success())

        with _make_client(svc, mock_user) as client:
            response = client.post("/api/v1/calculations/", json=_CALC_BODY)

        assert response.status_code == 201
        data = response.json()
        assert data["snapshot_id"] == str(_SNAP_ID)
        assert data["deal_status"] == "ANALYSED"
        assert data["snapshot"]["outputs"]["annual_cash_flow_gbp"] == "-331.90"
        assert data["snapshot"]["outputs"]["monthly_cash_flow_gbp"] == "-27.66"

    def test_non_owned_deal_returns_404(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.run_calculation = AsyncMock(
            side_effect=NotFoundError(entity="deal", id=_DEAL_ID)
        )

        with _make_client(svc, mock_user) as client:
            response = client.post("/api/v1/calculations/", json=_CALC_BODY)

        assert response.status_code == 404

    def test_validation_failure_returns_422_with_field_errors(
        self, mock_user: User
    ) -> None:
        from app.engine.contracts import ValidationError

        svc = MagicMock()
        svc.run_calculation = AsyncMock(
            return_value=SvcCalculationValidationFailure(
                hard_errors=[
                    ValidationError(
                        rule_code="V-07",
                        field="deposit_amount",
                        message="Deposit must be at least 15% of purchase price",
                    )
                ],
                warnings=[],
            )
        )

        with _make_client(svc, mock_user) as client:
            response = client.post("/api/v1/calculations/", json=_CALC_BODY)

        assert response.status_code == 422
        body = response.json()
        assert "field_errors" in body
        assert body["field_errors"][0]["rule_code"] == "V-07"
        assert body["field_errors"][0]["field"] == "deposit_amount"

    def test_engine_error_returns_500(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.run_calculation = AsyncMock(
            return_value=SvcCalculationError(
                message="Calculation could not be completed."
            )
        )

        with _make_client(svc, mock_user) as client:
            response = client.post("/api/v1/calculations/", json=_CALC_BODY)

        assert response.status_code == 500

    def test_archived_deal_returns_422(self, mock_user: User) -> None:
        from app.domain.errors import DomainError

        svc = MagicMock()
        svc.run_calculation = AsyncMock(
            side_effect=DomainError("Cannot calculate on an archived deal")
        )

        with _make_client(svc, mock_user) as client:
            response = client.post("/api/v1/calculations/", json=_CALC_BODY)

        assert response.status_code == 422

    def test_missing_required_field_returns_422(self, mock_user: User) -> None:
        svc = MagicMock()
        body = {k: v for k, v in _CALC_BODY.items() if k != "purchase_price"}

        with _make_client(svc, mock_user) as client:
            response = client.post("/api/v1/calculations/", json=body)

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/calculations/recalculate
# ---------------------------------------------------------------------------


class TestRecalculate:
    def test_returns_201_with_snapshot_summary(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.recalculate_with_current_assumptions = AsyncMock(
            return_value=_make_success()
        )

        with _make_client(svc, mock_user) as client:
            response = client.post(
                "/api/v1/calculations/recalculate",
                json={"deal_id": str(_DEAL_ID)},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["snapshot_id"] == str(_SNAP_ID)
        assert data["deal_status"] == "ANALYSED"

    def test_non_owned_deal_returns_404(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.recalculate_with_current_assumptions = AsyncMock(
            side_effect=NotFoundError(entity="deal", id=_DEAL_ID)
        )

        with _make_client(svc, mock_user) as client:
            response = client.post(
                "/api/v1/calculations/recalculate",
                json={"deal_id": str(_DEAL_ID)},
            )

        assert response.status_code == 404

    def test_incomplete_inputs_returns_422(self, mock_user: User) -> None:
        from app.domain.errors import DomainError

        svc = MagicMock()
        svc.recalculate_with_current_assumptions = AsyncMock(
            side_effect=DomainError(
                "Deal working inputs are incomplete for recalculation: purchase_price"
            )
        )

        with _make_client(svc, mock_user) as client:
            response = client.post(
                "/api/v1/calculations/recalculate",
                json={"deal_id": str(_DEAL_ID)},
            )

        assert response.status_code == 422

    def test_validation_failure_returns_422_with_field_errors(
        self, mock_user: User
    ) -> None:
        from app.engine.contracts import ValidationError

        svc = MagicMock()
        svc.recalculate_with_current_assumptions = AsyncMock(
            return_value=SvcCalculationValidationFailure(
                hard_errors=[
                    ValidationError(
                        rule_code="V-01",
                        field="purchase_price",
                        message="Purchase price must be greater than zero.",
                    )
                ],
                warnings=[],
            )
        )

        with _make_client(svc, mock_user) as client:
            response = client.post(
                "/api/v1/calculations/recalculate",
                json={"deal_id": str(_DEAL_ID)},
            )

        assert response.status_code == 422
        assert "field_errors" in response.json()


# ---------------------------------------------------------------------------
# POST /api/v1/calculations/reproduce-original
# ---------------------------------------------------------------------------


class TestReproduceOriginal:
    def test_returns_201_with_snapshot_summary(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.reproduce_original = AsyncMock(return_value=_make_success())

        with _make_client(svc, mock_user) as client:
            response = client.post(
                "/api/v1/calculations/reproduce-original",
                json={"source_snapshot_id": str(_SNAP_ID)},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["snapshot_id"] == str(_SNAP_ID)

    def test_non_owned_snapshot_returns_404(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.reproduce_original = AsyncMock(
            side_effect=NotFoundError(entity="snapshot", id=_SNAP_ID)
        )

        with _make_client(svc, mock_user) as client:
            response = client.post(
                "/api/v1/calculations/reproduce-original",
                json={"source_snapshot_id": str(_SNAP_ID)},
            )

        assert response.status_code == 404

    def test_missing_source_snapshot_id_returns_422(self, mock_user: User) -> None:
        svc = MagicMock()

        with _make_client(svc, mock_user) as client:
            response = client.post(
                "/api/v1/calculations/reproduce-original",
                json={},
            )

        assert response.status_code == 422
