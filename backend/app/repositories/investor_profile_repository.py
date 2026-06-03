"""
InvestorProfileRepository — SQLAlchemy implementation of IInvestorProfileRepository.

Architecture:
    REPOSITORY_ARCHITECTURE.md Part 2.5, 5.5.
    DATABASE_SCHEMA_DESIGN.md Section 2 — investor_profiles table.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.investor_profile import InvestorProfile as InvestorProfileORM
from app.domain.entities.investor_profile import InvestorProfile
from app.domain.enums import IncomeTaxBand, OwnershipStructure


class InvestorProfileRepository:
    """
    SQLAlchemy implementation of IInvestorProfileRepository.

    Receives AsyncSession as a constructor dependency.
    Does not commit — the caller manages session lifecycle.

    Architecture: REPOSITORY_ARCHITECTURE.md Part 13.1–13.3.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, profile: InvestorProfile) -> None:
        """Create a new investor profile record."""
        row = InvestorProfileORM(
            id=profile.id,
            user_id=profile.user_id,
            label=profile.label,
            ownership_structure=profile.ownership_structure,
            income_tax_band=profile.income_tax_band,
            is_default=profile.is_default,
            is_archived=profile.is_archived,
            archived_at=profile.archived_at,
        )
        self._session.add(row)

    async def update(self, profile: InvestorProfile) -> None:
        """
        Persist mutable field updates: label, ownership_structure, income_tax_band,
        is_default, is_archived, archived_at.

        Never updates id, user_id, or created_at.
        """
        stmt = (
            update(InvestorProfileORM)
            .where(InvestorProfileORM.id == profile.id)
            .values(
                label=profile.label,
                ownership_structure=profile.ownership_structure,
                income_tax_band=profile.income_tax_band,
                is_default=profile.is_default,
                is_archived=profile.is_archived,
                archived_at=profile.archived_at,
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.execute(stmt)

    async def find_by_id(self, profile_id: uuid.UUID) -> InvestorProfile | None:
        """Return the profile with this id, or None if not found."""
        stmt = select(InvestorProfileORM).where(InvestorProfileORM.id == profile_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    async def find_by_id_for_user(
        self, profile_id: uuid.UUID, user_id: uuid.UUID
    ) -> InvestorProfile | None:
        """
        Ownership-aware load.
        Returns None if not found OR if the profile belongs to a different user.
        Never distinguishes between the two cases (RI-06).
        """
        stmt = select(InvestorProfileORM).where(
            InvestorProfileORM.id == profile_id,
            InvestorProfileORM.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    async def find_all_for_user(
        self, user_id: uuid.UUID, include_archived: bool = False
    ) -> list[InvestorProfile]:
        """
        All profiles for a user, newest first.

        include_archived=False filters out archived profiles.
        Not paginated: expected upper bound < 10 profiles per user (RI-09).
        """
        stmt = select(InvestorProfileORM).where(
            InvestorProfileORM.user_id == user_id
        )
        if not include_archived:
            stmt = stmt.where(InvestorProfileORM.is_archived.is_(False))
        stmt = stmt.order_by(InvestorProfileORM.created_at.desc())
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_domain(row) for row in rows]

    async def find_default_for_user(
        self, user_id: uuid.UUID
    ) -> InvestorProfile | None:
        """
        Return the profile with is_default=True for this user.
        Returns None if the user has no default profile set.
        """
        stmt = select(InvestorProfileORM).where(
            InvestorProfileORM.user_id == user_id,
            InvestorProfileORM.is_default.is_(True),
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    # ------------------------------------------------------------------
    # Private mapping helpers
    # ------------------------------------------------------------------

    def _to_domain(self, row: InvestorProfileORM) -> InvestorProfile:
        """Convert InvestorProfileORM row → InvestorProfile domain entity."""
        ownership_structure = (
            row.ownership_structure
            if isinstance(row.ownership_structure, OwnershipStructure)
            else OwnershipStructure(row.ownership_structure)
        )
        income_tax_band: IncomeTaxBand | None = None
        if row.income_tax_band is not None:
            income_tax_band = (
                row.income_tax_band
                if isinstance(row.income_tax_band, IncomeTaxBand)
                else IncomeTaxBand(row.income_tax_band)
            )
        return InvestorProfile(
            id=row.id,
            user_id=row.user_id,
            label=row.label,
            ownership_structure=ownership_structure,
            income_tax_band=income_tax_band,
            is_default=row.is_default,
            is_archived=row.is_archived,
            archived_at=row.archived_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
