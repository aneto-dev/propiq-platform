"""
Property CRUD API tests.

Covers:
    POST   /api/v1/properties/              201 + 422 (domain error)
    GET    /api/v1/properties/              200 list
    GET    /api/v1/properties/{id}/         200 + 404
    PATCH  /api/v1/properties/{id}/         200 + 404
    DELETE /api/v1/properties/{id}/archive  200 + 404

All tests use the mock-authenticated client from conftest.py.
The PropertyService is replaced with an AsyncMock so no DB is required.

Architecture:
    IMPLEMENTATION_ROADMAP.md Commit 6.3.
    AUTHORIZATION_MODEL.md §9.2 — auth as FastAPI dependency.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_property_service
from app.domain.entities.property import Property
from app.domain.entities.user import User
from app.domain.enums import PropertyType, Tenure
from app.domain.errors import DomainError, NotFoundError
from app.domain.value_objects.address import PropertyAddress
from app.main import create_app
from app.repositories.pagination import Page

# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

_PROP_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

_CREATE_BODY = {
    "address_line_1": "1 Test Street",
    "city": "London",
    "postcode": "SW1A 1AA",
    "property_type": "RESIDENTIAL_SINGLE_LET",
    "tenure": "FREEHOLD",
}


def _make_property(
    prop_id: uuid.UUID = _PROP_ID,
    is_archived: bool = False,
) -> Property:
    return Property(
        id=prop_id,
        user_id=_USER_ID,
        address=PropertyAddress(
            address_line_1="1 Test Street",
            address_line_2=None,
            city="London",
            postcode="SW1A 1AA",
        ),
        property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
        tenure=Tenure.FREEHOLD,
        lease_years_remaining=None,
        bedrooms=None,
        epc_rating=None,
        is_archived=is_archived,
        archived_at=_NOW if is_archived else None,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_client(mock_svc: object, mock_user: User) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_property_service] = lambda: mock_svc
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /api/v1/properties/
# ---------------------------------------------------------------------------


class TestCreateProperty:
    def test_returns_201_and_property_body(self, mock_user: User) -> None:
        prop = _make_property()
        svc = MagicMock()
        svc.create_property = AsyncMock(return_value=prop)

        with _make_client(svc, mock_user) as client:
            response = client.post("/api/v1/properties/", json=_CREATE_BODY)

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == str(_PROP_ID)
        assert data["tenure"] == "FREEHOLD"
        assert data["is_archived"] is False

    def test_leasehold_domain_error_returns_422(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.create_property = AsyncMock(
            side_effect=DomainError("Lease details required for leasehold properties")
        )

        body = {**_CREATE_BODY, "tenure": "LEASEHOLD"}
        with _make_client(svc, mock_user) as client:
            response = client.post("/api/v1/properties/", json=body)

        assert response.status_code == 422

    def test_missing_required_field_returns_422(self, mock_user: User) -> None:
        svc = MagicMock()
        body = {k: v for k, v in _CREATE_BODY.items() if k != "address_line_1"}
        with _make_client(svc, mock_user) as client:
            response = client.post("/api/v1/properties/", json=body)

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/properties/
# ---------------------------------------------------------------------------


class TestListProperties:
    def test_returns_200_with_list(self, mock_user: User) -> None:
        props = [_make_property(), _make_property(prop_id=uuid.uuid4())]
        svc = MagicMock()
        svc.list_properties = AsyncMock(
            return_value=Page(items=props, next_cursor=None, total_count=2)
        )

        with _make_client(svc, mock_user) as client:
            response = client.get("/api/v1/properties/")

        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_returns_empty_list(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.list_properties = AsyncMock(
            return_value=Page(items=[], next_cursor=None, total_count=0)
        )

        with _make_client(svc, mock_user) as client:
            response = client.get("/api/v1/properties/")

        assert response.status_code == 200
        assert response.json() == []

    def test_include_archived_query_param_forwarded(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.list_properties = AsyncMock(
            return_value=Page(items=[], next_cursor=None, total_count=0)
        )

        with _make_client(svc, mock_user) as client:
            client.get("/api/v1/properties/?include_archived=true")

        svc.list_properties.assert_called_once()
        _, kwargs = svc.list_properties.call_args
        assert kwargs.get("include_archived") is True


# ---------------------------------------------------------------------------
# GET /api/v1/properties/{id}/
# ---------------------------------------------------------------------------


class TestGetProperty:
    def test_returns_200_for_owned_property(self, mock_user: User) -> None:
        prop = _make_property()
        svc = MagicMock()
        svc.get_property_for_user = AsyncMock(return_value=prop)

        with _make_client(svc, mock_user) as client:
            response = client.get(f"/api/v1/properties/{_PROP_ID}")

        assert response.status_code == 200
        assert response.json()["id"] == str(_PROP_ID)

    def test_returns_404_for_not_found(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.get_property_for_user = AsyncMock(
            side_effect=NotFoundError(entity="property", id=_PROP_ID)
        )

        with _make_client(svc, mock_user) as client:
            response = client.get(f"/api/v1/properties/{_PROP_ID}")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/properties/{id}/
# ---------------------------------------------------------------------------


class TestUpdateProperty:
    def test_returns_200_with_updated_data(self, mock_user: User) -> None:
        prop = _make_property()
        svc = MagicMock()
        svc.update_property = AsyncMock(return_value=prop)

        with _make_client(svc, mock_user) as client:
            response = client.patch(
                f"/api/v1/properties/{_PROP_ID}", json=_CREATE_BODY
            )

        assert response.status_code == 200
        assert response.json()["id"] == str(_PROP_ID)

    def test_returns_404_for_not_found(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.update_property = AsyncMock(
            side_effect=NotFoundError(entity="property", id=_PROP_ID)
        )

        with _make_client(svc, mock_user) as client:
            response = client.patch(
                f"/api/v1/properties/{_PROP_ID}", json=_CREATE_BODY
            )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/properties/{id}/archive
# ---------------------------------------------------------------------------


class TestArchiveProperty:
    def test_returns_200_with_archived_property(self, mock_user: User) -> None:
        prop = _make_property(is_archived=True)
        svc = MagicMock()
        svc.archive_property = AsyncMock(return_value=prop)

        with _make_client(svc, mock_user) as client:
            response = client.delete(f"/api/v1/properties/{_PROP_ID}/archive")

        assert response.status_code == 200
        assert response.json()["is_archived"] is True

    def test_returns_404_for_not_found(self, mock_user: User) -> None:
        svc = MagicMock()
        svc.archive_property = AsyncMock(
            side_effect=NotFoundError(entity="property", id=_PROP_ID)
        )

        with _make_client(svc, mock_user) as client:
            response = client.delete(f"/api/v1/properties/{_PROP_ID}/archive")

        assert response.status_code == 404
