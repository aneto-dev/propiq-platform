"""
FastAPI dependency functions for authentication and database session management.

Provides:

  get_db() → AsyncGenerator[AsyncSession]
      Yields a per-request AsyncSession from the application engine.
      Session is closed after the request completes.

  get_current_user() → User
      FastAPI dependency. Verifies the Supabase JWT (RS256, JWKS) and
      resolves the platform user via UserService.get_or_create_user().
      Raises HTTP 401 on any verification failure.

  get_user_service(db) → UserService
      FastAPI dependency. Constructs a UserService bound to the request session.

JWT verification:
  Supabase issues RS256-signed JWTs. Verification uses the public keys
  from Supabase's JWKS endpoint: {supabase_url}/.well-known/jwks.json
  The `sub` claim is the Supabase user UUID (stable across sessions).
  No shared secret / HS256 verification — RS256 only (AUTHORIZATION_MODEL.md §1.2).

Architecture:
    AUTHORIZATION_MODEL.md §1.2, §9.2.
    IMPLEMENTATION_ROADMAP.md Commit 6.1.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

import httpx
from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.domain.entities.user import User
from app.repositories.deal_repository import DealRepository
from app.repositories.investor_profile_repository import InvestorProfileRepository
from app.repositories.property_repository import PropertyRepository
from app.repositories.user_repository import UserRepository
from app.services.deal_service import DealService
from app.services.property_service import PropertyService
from app.services.user_service import UserService

# ---------------------------------------------------------------------------
# Application-level engine — created once, shared across requests.
# NullPool is used because asyncpg connections cannot be shared across
# OS threads. For production, swap NullPool for AsyncAdaptedQueuePool.
# ---------------------------------------------------------------------------

_app_engine: AsyncEngine | None = None
_app_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    global _app_engine
    if _app_engine is None:
        settings = get_settings()
        _app_engine = create_async_engine(
            settings.database_url or settings.test_database_url,
            echo=False,
            poolclass=NullPool,
        )
    return _app_engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _app_session_factory
    if _app_session_factory is None:
        _app_session_factory = async_sessionmaker(_get_engine(), expire_on_commit=False)
    return _app_session_factory


# ---------------------------------------------------------------------------
# Database session dependency
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession]:
    """
    Yield a per-request AsyncSession.

    The session is closed (and the connection returned to the pool)
    after the route handler completes, regardless of success or failure.
    """
    factory = _get_session_factory()
    async with factory() as session:
        yield session


# ---------------------------------------------------------------------------
# User service dependency
# ---------------------------------------------------------------------------

def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    """Construct a UserService bound to the request session."""
    return UserService(UserRepository(db))


def get_property_service(db: AsyncSession = Depends(get_db)) -> PropertyService:
    """Construct a PropertyService bound to the request session."""
    return PropertyService(PropertyRepository(db))


def get_deal_service(db: AsyncSession = Depends(get_db)) -> DealService:
    """Construct a DealService bound to the request session."""
    return DealService(
        deal_repo=DealRepository(db),
        property_repo=PropertyRepository(db),
        profile_repo=InvestorProfileRepository(db),
    )


# ---------------------------------------------------------------------------
# JWKS fetching — cached per process lifetime
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_jwks() -> dict[str, list[dict[str, str]]]:
    """
    Fetch Supabase's JWKS (JSON Web Key Set) and cache for the process lifetime.

    JWKS rotation is rare (typically on key compromise). For production,
    add cache invalidation or a TTL. For Phase 1, process-lifetime caching
    is sufficient.

    Architecture: AUTHORIZATION_MODEL.md §1.2 — RS256 public key verification.
    """
    settings = get_settings()
    if not settings.supabase_url:
        # In test environments supabase_url may be empty; return an empty JWKS.
        # get_current_user will raise 401 if called without a valid config.
        return {"keys": []}
    jwks_url = f"{settings.supabase_url.rstrip('/')}/.well-known/jwks.json"
    response = httpx.get(jwks_url, timeout=10.0)
    response.raise_for_status()
    result: dict[str, list[dict[str, str]]] = response.json()
    return result


# ---------------------------------------------------------------------------
# JWT verification — RS256 / Supabase JWKS only
# ---------------------------------------------------------------------------

def _verify_jwt(token: str) -> dict[str, object]:
    """
    Verify a Supabase-issued JWT using RS256 and return the decoded claims.

    Steps:
      1. Decode the JWT header to get the key ID (kid).
      2. Find the matching public key in the JWKS.
      3. Verify the signature, expiry, and structure using python-jose.

    Raises HTTPException(401) on any failure.

    Algorithm: RS256 only. HS256 / shared-secret verification is not used.
    Architecture: AUTHORIZATION_MODEL.md §1.2.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decode header to find the kid
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        # Locate the matching key in the JWKS
        jwks = _get_jwks()
        matching_keys = [k for k in jwks.get("keys", []) if k.get("kid") == kid]
        if not matching_keys:
            raise credentials_exception

        # Verify signature, expiry, and decode claims
        # algorithms=["RS256"] — no HS256, no other algorithm accepted
        claims: dict[str, object] = jwt.decode(
            token,
            matching_keys[0],
            algorithms=["RS256"],
            options={"verify_aud": False},  # Supabase JWTs omit explicit audience
        )
        return claims

    except JWTError as exc:
        raise credentials_exception from exc


# ---------------------------------------------------------------------------
# Authentication dependency — the primary FastAPI auth entry point
# ---------------------------------------------------------------------------

async def get_current_user(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """
    FastAPI dependency: verify the Supabase JWT and return the platform User.

    Steps:
      1. Extract the Bearer token from the Authorization header.
      2. Verify the JWT signature (RS256, Supabase JWKS).
      3. Extract the `sub` claim (Supabase user UUID).
      4. Call UserService.get_or_create_user() to resolve the platform user,
         creating a record on first login if necessary.
      5. Return the authenticated platform User entity.

    Raises HTTP 401 on any verification failure.
    The platform user UUID (not the Supabase sub) is used throughout
    the service and domain layers.

    Architecture: AUTHORIZATION_MODEL.md §1.2, §9.2.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Extract Bearer token
    if not authorization.startswith("Bearer "):
        raise credentials_exception
    token = authorization[len("Bearer "):]

    # Verify JWT and extract claims
    claims = _verify_jwt(token)

    supabase_auth_id_str = str(claims.get("sub", ""))
    email = str(claims.get("email", ""))
    if not supabase_auth_id_str:
        raise credentials_exception

    try:
        import uuid
        supabase_auth_id = uuid.UUID(supabase_auth_id_str)
    except ValueError as exc:
        raise credentials_exception from exc

    # Resolve platform user (creates on first login)
    user = await user_service.get_or_create_user(
        supabase_auth_id=supabase_auth_id,
        email=email,
    )
    await db.commit()
    return user
