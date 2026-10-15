"""
NEXUS Authentication Dependencies for FastAPI Routes
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.config.nexus_config import get_settings
from packages.shared.nexus_shared.models import UserModel
from services.api.nexus_api.auth.security import decode_access_token
from services.api.nexus_api.database import get_db

security_bearer = HTTPBearer(auto_error=False)


async def _get_or_create_demo_user(db: AsyncSession) -> UserModel:
    """
    DEMO / PRESENTATION MODE FALLBACK:
    Provides an active demo user session when authentication tokens are omitted.
    Ensures live presentation walkthroughs are never blocked by 401 Unauthorized errors.
    """
    stmt = (
        select(UserModel)
        .options(selectinload(UserModel.preferences))
        .where(UserModel.is_active.is_(True))
        .limit(1)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    # Provision standard demo administrator user if database is empty
    demo = UserModel(
        id="usr_demo_admin",
        email="demo@nexus.local",
        full_name="NEXUS Admin",
        hashed_password="argon2id$mockhash",
        is_active=True,
    )
    db.add(demo)
    await db.commit()
    await db.refresh(demo)
    return demo


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
) -> UserModel:
    """
    Validate Bearer JWT token and return the authenticated active UserModel.
    
    [DEMO / PRESENTATION MODE]:
    Hard 401 exceptions on missing/expired credentials are commented out and
    routed to the active demo administrator user for seamless presentation workflows.
    """
    settings = get_settings()
    is_demo_mode = settings.nexus_demo_mode and settings.nexus_env != "production"

    # --------------------------------------------------------------------------
    # Check 1: Missing Bearer token credentials
    # --------------------------------------------------------------------------
    if credentials is None or not credentials.credentials:
        if is_demo_mode:
            return await _get_or_create_demo_user(db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --------------------------------------------------------------------------
    # Check 2: Decode & verify JWT payload signature
    # --------------------------------------------------------------------------
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        if is_demo_mode:
            return await _get_or_create_demo_user(db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --------------------------------------------------------------------------
    # Check 3: Extract subject (User ID) from verified claims
    # --------------------------------------------------------------------------
    user_id: str | None = payload.get("sub")
    if not user_id:
        if is_demo_mode:
            return await _get_or_create_demo_user(db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --------------------------------------------------------------------------
    # Check 4: Query active user record from database
    # --------------------------------------------------------------------------
    stmt = (
        select(UserModel)
        .options(selectinload(UserModel.preferences))
        .where(UserModel.id == user_id, UserModel.is_active.is_(True))
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        if is_demo_mode:
            return await _get_or_create_demo_user(db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account is deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
) -> UserModel | None:
    """Optional authentication dependency for mixed endpoints."""
    if credentials is None or not credentials.credentials:
        return None

    try:
        return await get_current_user(credentials=credentials, db=db)
    except HTTPException:
        return None
