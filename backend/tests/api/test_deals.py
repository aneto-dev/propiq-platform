"""
Deal CRUD API tests.

Covers:
    POST  /api/v1/deals/                    201 + 404 (property not found)
    GET   /api/v1/deals/                    200 list
    GET   /api/v1/deals/{id}/               200 + 404
    PATCH /api/v1/deals/{id}/inputs         200 + 404 + 422 (archived guard)
    POST  /api/v1/deals/{id}/archive        200 + 404

All tests use the mock-authenticated client from conftest.py.
The DealService is replaced with an AsyncMock so no DB is required.

Architecture:
    IMPLEMENTATION_ROADMAP.md Commit 6.3.
    AUTHORIZATION_MODEL.md §9.2 — auth as FastAPI dependency.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_deal_service
from app.domain.entities.deal import Deal, DealWorkingInputs
from app.domain.entities.user import User
from app.domain.enums import DealStatus
from app.domain.errors import DomainError, NotFoundError
from app.main import create_app
from app.repositories.interfaces.i_deal import DealSummary
from app.repositories.pagination import Page

# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

_DEAL_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
_PROP_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _make_deal(
    deal_id: uuid.UUID = _DEAL_ID,
    status: DealStatus = DealStatus.DRAFT,
) -> Deal:
    return Deal(
        id=deal_id,
        user_id=_USER_ID,
        property_id=_PROP_ID,
        label="Test Deal",
        status=status,
        working_inputs=DealWorkingInputs(),
        latest_snapshot_id=None,
        investor_profile_id=None,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_summary(deal_id: uuid.UUID = _DEAL_ID) -> DealSummary:
    return DealSummary(
        id=deal_id,
        label="Test Deal",
        status=DealStatus.DRAFT,
        property_id=_PROP_ID,
        latest_snapshot_id=None,
        created_at=_NOW,
        updated_at=_NOW,
        latest_snapshot_cash_flow_gbp=None,
        latest_snapshot_gross_yield=None,
        latest_snapshot_calculated_at=None,
        latest_snapshot_risk_flag_count_high=None,
    )


def _make_client(mock_svc: object, mock_user: User) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_deal_service] = lambda: mock_svc
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /api/v1/deals/
# ---------------------------------------------------------------------------


class TestCreateDeal:
    def test_returns_201_with_deal_body(self, mock_user: User) -> None:
        deal = _make_deal()
        svc = MagicMock()
        svc.create_deal = AsyncMock(return_value=deal)

        with _make_client(svc, mock_user) as client:
            response = client.post(
                "/api/v1/deals/",
                params={"property_id": str(_PROP_ID), "label": "Test Deal"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == str(_DEAL_ID)
        assert data["status"] == "DRAFT"
        assert data["property_id"] == str(_PROP_ID)

    def test_property_not_found_returns_404(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.create_deal = AsyncMock(
            side_effect=NotFoundError(entity="property", id=_PROP_ID)
        )

        with _make_client(svc, mock_user) as client:
            response = client.post(
                "/api/v1/deals/",
                params={"property_id": str(_PROP_ID), "label": "Test Deal"},
            )

        assert response.status_code == 404

    def test_missing_label_returns_422(self, mock_user: User) -> None:
        svc = MagicMock()
        with _make_client(svc, mock_user) as client:
            response = client.post(
                "/api/v1/deals/",
                params={"property_id": str(_PROP_ID)},
            )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/deals/
# ---------------------------------------------------------------------------


class TestListDeals:
    def test_returns_200_with_summaries(self, mock_user: User) -> None:
        summaries = [_make_summary(), _make_summary(deal_id=uuid.uuid4())]
        svc = MagicMock()
        svc.list_deals = AsyncMock(
            return_value=Page(items=summaries, next_cursor=None, total_count=2)
        )

        with _make_client(svc, mock_user) as client:
            response = client.get("/api/v1/deals/")

        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_returns_empty_list(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.list_deals = AsyncMock(return_value=Page(items=[], next_cursor=None, total_count=0))

        with _make_client(svc, mock_user) as client:
            response = client.get("/api/v1/deals/")

        assert response.status_code == 200
        assert response.json() == []

    def test_status_filter_forwarded_to_service(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.list_deals = AsyncMock(return_value=Page(items=[], next_cursor=None, total_count=0))

        with _make_client(svc, mock_user) as client:
            client.get("/api/v1/deals/?status_filter=DRAFT")

        svc.list_deals.assert_called_once()
        _, kwargs = svc.list_deals.call_args
        assert kwargs.get("status_filter") == DealStatus.DRAFT


# ---------------------------------------------------------------------------
# GET /api/v1/deals/{id}/
# ---------------------------------------------------------------------------


class TestGetDeal:
    def test_returns_200_for_owned_deal(self, mock_user: User) -> None:
        deal = _make_deal()
        svc = MagicMock()
        svc.get_deal = AsyncMock(return_value=deal)

        with _make_client(svc, mock_user) as client:
            response = client.get(f"/api/v1/deals/{_DEAL_ID}")

        assert response.status_code == 200
        assert response.json()["id"] == str(_DEAL_ID)

    def test_returns_404_for_not_found(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.get_deal = AsyncMock(
            side_effect=NotFoundError(entity="deal", id=_DEAL_ID)
        )

        with _make_client(svc, mock_user) as client:
            response = client.get(f"/api/v1/deals/{_DEAL_ID}")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/deals/{id}/inputs
# ---------------------------------------------------------------------------


class TestUpdateWorkingInputs:
    def test_returns_200_with_updated_deal(self, mock_user: User) -> None:
        deal = _make_deal()
        svc = MagicMock()
        svc.update_working_inputs = AsyncMock(return_value=deal)

        with _make_client(svc, mock_user) as client:
            response = client.patch(
                f"/api/v1/deals/{_DEAL_ID}/inputs",
                json={"purchase_price": "200000.00"},
            )

        assert response.status_code == 200
        assert response.json()["id"] == str(_DEAL_ID)

    def test_returns_404_for_not_found(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.update_working_inputs = AsyncMock(
            side_effect=NotFoundError(entity="deal", id=_DEAL_ID)
        )

        with _make_client(svc, mock_user) as client:
            response = client.patch(
                f"/api/v1/deals/{_DEAL_ID}/inputs",
                json={"purchase_price": "200000.00"},
            )

        assert response.status_code == 404

    def test_updating_archived_deal_returns_422(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.update_working_inputs = AsyncMock(
            side_effect=DomainError("Cannot update archived deal")
        )

        with _make_client(svc, mock_user) as client:
            response = client.patch(
                f"/api/v1/deals/{_DEAL_ID}/inputs",
                json={"purchase_price": "200000.00"},
            )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/deals/{id}/advance
# ---------------------------------------------------------------------------


class TestAdvanceDealStatus:
    def test_returns_200_with_advanced_deal(self, mock_user: User) -> None:
        deal = _make_deal(status=DealStatus.OFFER_SUBMITTED)
        svc = MagicMock()
        svc.advance_deal_status = AsyncMock(return_value=deal)

        with _make_client(svc, mock_user) as client:
            response = client.post(f"/api/v1/deals/{_DEAL_ID}/advance")

        assert response.status_code == 200
        assert response.json()["status"] == "OFFER_SUBMITTED"

    def test_returns_404_for_not_found(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.advance_deal_status = AsyncMock(
            side_effect=NotFoundError(entity="deal", id=_DEAL_ID)
        )

        with _make_client(svc, mock_user) as client:
            response = client.post(f"/api/v1/deals/{_DEAL_ID}/advance")

        assert response.status_code == 404

    def test_returns_422_for_invalid_transition(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.advance_deal_status = AsyncMock(
            side_effect=DomainError("Cannot advance deal from status DRAFT.")
        )

        with _make_client(svc, mock_user) as client:
            response = client.post(f"/api/v1/deals/{_DEAL_ID}/advance")

        assert response.status_code == 422


# POST /api/v1/deals/{id}/archive
# ---------------------------------------------------------------------------


class TestArchiveDeal:
    def test_returns_200_with_archived_deal(self, mock_user: User) -> None:
        deal = _make_deal(status=DealStatus.ARCHIVED)
        svc = MagicMock()
        svc.archive_deal = AsyncMock(return_value=deal)

        with _make_client(svc, mock_user) as client:
            response = client.post(f"/api/v1/deals/{_DEAL_ID}/archive")

        assert response.status_code == 200
        assert response.json()["status"] == "ARCHIVED"

    def test_returns_404_for_not_found(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.archive_deal = AsyncMock(
            side_effect=NotFoundError(entity="deal", id=_DEAL_ID)
        )

        with _make_client(svc, mock_user) as client:
            response = client.post(f"/api/v1/deals/{_DEAL_ID}/archive")

        assert response.status_code == 404
