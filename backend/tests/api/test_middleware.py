"""
Correlation ID middleware tests.

Verifies:
  - X-Correlation-ID is present on every response (Phase 6 exit criterion)
  - Generated IDs follow the req_<uuid4> format
  - Client-supplied bare UUID is accepted and returned as req_<uuid>
  - Client-supplied req_<uuid> is echoed unchanged
  - Invalid / malformed client header causes a fresh ID to be generated (no 400)
  - Empty X-Correlation-ID header causes a fresh ID to be generated

Tests use the health endpoint (/api/v1/health/) which requires no auth,
exercising the middleware without any service-layer mocking.

Architecture:
    OBSERVABILITY_ARCHITECTURE.md Part 4.2 — correlation ID propagation.
    IMPLEMENTATION_ROADMAP.md Commit 6.6.
"""

from __future__ import annotations

import re
import uuid

from fastapi.testclient import TestClient

from app.main import create_app

# Pattern: req_ followed by a UUID4
_CORR_ID_RE = re.compile(
    r"^req_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_HEALTH_URL = "/api/v1/health/"


def _client() -> TestClient:
    """Fresh app instance for each test — no dependency overrides needed."""
    return TestClient(create_app(), raise_server_exceptions=False)


class TestCorrelationIdPresence:
    def test_every_response_has_correlation_id_header(self) -> None:
        """Phase 6 exit criterion: X-Correlation-ID present on all responses."""
        with _client() as client:
            response = client.get(_HEALTH_URL)
        assert "X-Correlation-ID" in response.headers

    def test_generated_id_matches_req_uuid4_format(self) -> None:
        """Generated correlation ID is 'req_' + UUID4."""
        with _client() as client:
            response = client.get(_HEALTH_URL)
        corr_id = response.headers["X-Correlation-ID"]
        assert _CORR_ID_RE.match(corr_id), f"Unexpected format: {corr_id!r}"

    def test_different_requests_get_different_correlation_ids(self) -> None:
        """Each request generates a unique correlation ID."""
        with _client() as client:
            r1 = client.get(_HEALTH_URL)
            r2 = client.get(_HEALTH_URL)
        assert r1.headers["X-Correlation-ID"] != r2.headers["X-Correlation-ID"]


class TestClientProvidedCorrelationId:
    def test_bare_uuid_is_accepted_and_normalised_to_req_prefix(self) -> None:
        """Client provides a plain UUID; middleware prefixes 'req_' and returns it."""
        client_uuid = str(uuid.uuid4())
        with _client() as client:
            response = client.get(
                _HEALTH_URL,
                headers={"X-Correlation-ID": client_uuid},
            )
        returned = response.headers["X-Correlation-ID"]
        assert returned == f"req_{client_uuid.lower()}"

    def test_req_prefixed_uuid_is_echoed_unchanged(self) -> None:
        """Client provides a canonical req_<uuid> value; echoed back unchanged."""
        client_id = f"req_{uuid.uuid4()}"
        with _client() as client:
            response = client.get(
                _HEALTH_URL,
                headers={"X-Correlation-ID": client_id},
            )
        assert response.headers["X-Correlation-ID"] == client_id

    def test_malformed_client_header_does_not_return_400(self) -> None:
        """Malformed X-Correlation-ID header never causes a 400 response."""
        with _client() as client:
            response = client.get(
                _HEALTH_URL,
                headers={"X-Correlation-ID": "not-a-valid-id"},
            )
        assert response.status_code != 400

    def test_malformed_client_header_generates_fresh_id(self) -> None:
        """Malformed X-Correlation-ID header results in a generated req_<uuid4>."""
        with _client() as client:
            response = client.get(
                _HEALTH_URL,
                headers={"X-Correlation-ID": "not-a-valid-id"},
            )
        corr_id = response.headers["X-Correlation-ID"]
        assert _CORR_ID_RE.match(corr_id), f"Expected generated ID, got: {corr_id!r}"

    def test_empty_client_header_generates_fresh_id(self) -> None:
        """Empty X-Correlation-ID header results in a generated req_<uuid4>."""
        with _client() as client:
            response = client.get(
                _HEALTH_URL,
                headers={"X-Correlation-ID": ""},
            )
        corr_id = response.headers["X-Correlation-ID"]
        assert _CORR_ID_RE.match(corr_id)

    def test_req_prefix_with_invalid_suffix_generates_fresh_id(self) -> None:
        """req_ prefix with non-UUID suffix is rejected; fresh ID generated."""
        with _client() as client:
            response = client.get(
                _HEALTH_URL,
                headers={"X-Correlation-ID": "req_not-a-uuid"},
            )
        corr_id = response.headers["X-Correlation-ID"]
        # Must be a fresh generated ID, not the invalid input
        assert corr_id != "req_not-a-uuid"
        assert _CORR_ID_RE.match(corr_id)


class TestCorrelationIdOnErrorResponses:
    def test_404_response_has_correlation_id(self) -> None:
        """X-Correlation-ID is present even on 404 Not Found responses."""
        with _client() as client:
            response = client.get("/api/v1/snapshots/no-such-id-here")
        assert "X-Correlation-ID" in response.headers

    def test_422_response_has_correlation_id(self) -> None:
        """X-Correlation-ID is present on 422 Unprocessable Entity responses."""
        with _client() as client:
            # POST to calculations/ with no body → 422 validation error
            response = client.post("/api/v1/calculations/", json={})
        assert "X-Correlation-ID" in response.headers
