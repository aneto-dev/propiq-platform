"""
Pagination value types for the repository layer.

PageRequest and Page[T] are the universal pagination contract used across
all list-returning repository methods.

Cursor encoding: base64 of JSON {"created_at": "<iso>", "id": "<uuid>"}.
This provides stable pagination even as records are inserted or updated
between page requests (cursor-based / keyset pagination).

Architecture: REPOSITORY_ARCHITECTURE.md Part 15.
"""

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class PageRequest:
    """
    Request parameters for a paginated list operation.

    limit: maximum records per page (1–100, default 20)
    cursor: opaque pagination cursor from a previous Page response;
            None for the first page.

    Architecture: REPOSITORY_ARCHITECTURE.md Part 15.1.
    """

    limit: int = 20
    cursor: str | None = None

    def __post_init__(self) -> None:
        if not (1 <= self.limit <= 100):
            raise ValueError(
                f"PageRequest.limit must be between 1 and 100, got {self.limit}"
            )

    def decode_cursor(self) -> tuple[datetime, uuid.UUID] | None:
        """
        Decode the cursor into (created_at, id) for keyset pagination.
        Returns None if cursor is None (first page).
        Raises ValueError if the cursor is malformed.
        """
        if self.cursor is None:
            return None
        try:
            payload = json.loads(base64.b64decode(self.cursor.encode()).decode())
            created_at = datetime.fromisoformat(payload["created_at"])
            record_id = uuid.UUID(payload["id"])
            return created_at, record_id
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f"Malformed pagination cursor: {self.cursor!r}") from exc


@dataclass(frozen=True)
class Page(Generic[T]):
    """
    A single page of results from a paginated list operation.

    items: the records on this page (may be empty on the last page)
    next_cursor: opaque cursor for the next page; None if this is the last page
    total_count: total number of matching records across all pages

    Architecture: REPOSITORY_ARCHITECTURE.md Part 15.1.
    """

    items: list[T]
    next_cursor: str | None
    total_count: int

    @staticmethod
    def encode_cursor(created_at: datetime, record_id: uuid.UUID) -> str:
        """
        Encode a (created_at, id) pair into an opaque cursor string.
        Used by repository implementations when building the next_cursor.
        """
        payload = {
            "created_at": created_at.isoformat(),
            "id": str(record_id),
        }
        return base64.b64encode(json.dumps(payload).encode()).decode()
