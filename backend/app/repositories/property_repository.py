"""
PropertyRepository — SQLAlchemy implementation of IPropertyRepository.

Architecture:
    REPOSITORY_ARCHITECTURE.md Part 2.3, 5.3.
    DATABASE_SCHEMA_DESIGN.md Section 2 — properties table.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.property import Property as PropertyORM
from app.domain.entities.property import Property
from app.domain.enums import PropertyCountry, PropertyType, Tenure
from app.domain.value_objects.address import PropertyAddress
from app.repositories.pagination import Page, PageRequest


class PropertyRepository:
    """
    SQLAlchemy implementation of IPropertyRepository.

    Receives AsyncSession as a constructor dependency.
    Does not commit — the caller manages session lifecycle.

    Tenure immutability: update() explicitly excludes tenure from the SET
    clause. If tenure is passed incorrectly the caller must archive the
    property and create a replacement.

    Architecture: REPOSITORY_ARCHITECTURE.md Part 13.1–13.3.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, property: Property) -> None:
        """Persist a new property (INSERT)."""
        row = PropertyORM(
            id=property.id,
            user_id=property.user_id,
            address_line_1=property.address.address_line_1,
            address_line_2=property.address.address_line_2,
            city=property.address.city,
            postcode=property.address.postcode,
            property_type=property.property_type,
            tenure=property.tenure,
            lease_years_remaining=property.lease_years_remaining,
            bedrooms=property.bedrooms,
            epc_rating=property.epc_rating,
            is_archived=property.is_archived,
            archived_at=property.archived_at,
        )
        self._session.add(row)

    async def update(self, property: Property) -> None:
        """
        Persist mutable field updates: address fields, property_type, bedrooms,
        epc_rating, is_archived, archived_at.

        Never updates id, user_id, tenure, or created_at (RI-05).
        """
        stmt = (
            update(PropertyORM)
            .where(PropertyORM.id == property.id)
            .values(
                address_line_1=property.address.address_line_1,
                address_line_2=property.address.address_line_2,
                city=property.address.city,
                postcode=property.address.postcode,
                property_type=property.property_type,
                bedrooms=property.bedrooms,
                epc_rating=property.epc_rating,
                is_archived=property.is_archived,
                archived_at=property.archived_at,
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.execute(stmt)

    async def find_by_id(self, property_id: uuid.UUID) -> Property | None:
        """Return the property with this id, or None if not found."""
        stmt = select(PropertyORM).where(PropertyORM.id == property_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    async def find_by_id_for_user(
        self, property_id: uuid.UUID, user_id: uuid.UUID
    ) -> Property | None:
        """
        Ownership-aware load.
        Returns None if not found OR if the property belongs to a different user.
        Never distinguishes between the two cases (RI-06).
        """
        stmt = select(PropertyORM).where(
            PropertyORM.id == property_id,
            PropertyORM.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    async def find_all_for_user(
        self,
        user_id: uuid.UUID,
        include_archived: bool,
        page: PageRequest,
    ) -> Page[Property]:
        """
        Paginated list of properties for a user, newest first.

        include_archived=False excludes archived properties.
        Uses keyset pagination on (created_at DESC, id DESC).

        Architecture: REPOSITORY_ARCHITECTURE.md Part 15.2.
        """
        # --- count query ---
        count_stmt = select(func.count()).select_from(PropertyORM).where(
            PropertyORM.user_id == user_id
        )
        if not include_archived:
            count_stmt = count_stmt.where(PropertyORM.is_archived.is_(False))
        count_result = await self._session.execute(count_stmt)
        total_count = count_result.scalar_one()

        # --- list query ---
        stmt = select(PropertyORM).where(PropertyORM.user_id == user_id)
        if not include_archived:
            stmt = stmt.where(PropertyORM.is_archived.is_(False))

        cursor = page.decode_cursor()
        if cursor is not None:
            cursor_created_at, cursor_id = cursor
            stmt = stmt.where(
                (PropertyORM.created_at < cursor_created_at)
                | (
                    (PropertyORM.created_at == cursor_created_at)
                    & (PropertyORM.id < cursor_id)
                )
            )

        stmt = stmt.order_by(
            PropertyORM.created_at.desc(),
            PropertyORM.id.desc(),
        ).limit(page.limit + 1)

        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        has_next = len(rows) > page.limit
        if has_next:
            rows = rows[: page.limit]

        items = [self._to_domain(row) for row in rows]

        next_cursor: str | None = None
        if has_next and rows:
            last = rows[-1]
            next_cursor = Page.encode_cursor(last.created_at, last.id)

        return Page(items=items, next_cursor=next_cursor, total_count=total_count)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _to_domain(self, row: PropertyORM) -> Property:
        """Convert PropertyORM row → Property domain entity."""
        property_type = (
            row.property_type
            if isinstance(row.property_type, PropertyType)
            else PropertyType(row.property_type)
        )
        tenure = (
            row.tenure
            if isinstance(row.tenure, Tenure)
            else Tenure(row.tenure)
        )
        address = PropertyAddress(
            address_line_1=row.address_line_1,
            address_line_2=row.address_line_2,
            city=row.city,
            postcode=row.postcode,
            country=PropertyCountry.ENGLAND,
        )
        return Property(
            id=row.id,
            user_id=row.user_id,
            address=address,
            property_type=property_type,
            tenure=tenure,
            lease_years_remaining=row.lease_years_remaining,
            bedrooms=row.bedrooms,
            epc_rating=row.epc_rating,
            is_archived=row.is_archived,
            archived_at=row.archived_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
