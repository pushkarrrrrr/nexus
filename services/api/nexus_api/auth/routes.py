"""
NEXUS Authentication & User Context API Endpoints
"""

from datetime import UTC, datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.config.nexus_config import get_settings
from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import (
    AuditLogModel,
    UserModel,
    UserPreferenceModel,
)
from packages.types.nexus_types.schemas import (
    ModelPreferences,
    PermissionPreferences,
    PrivacySettings,
    TokenResponse,
    UpdatePreferencesRequest,
    UserLoginRequest,
    UserPreferences,
    UserProfile,
    UserRegisterRequest,
)
from services.api.nexus_api.auth.dependencies import get_current_user
from services.api.nexus_api.auth.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from services.api.nexus_api.database import get_db

logger = get_logger("nexus.auth")
auth_router = APIRouter(prefix="/auth", tags=["auth"])


def _format_user_profile(user: UserModel) -> UserProfile:
    """Helper to convert UserModel to UserProfile schema."""
    prefs = None
    if user.preferences:
        raw_model_prefs = dict(user.preferences.model_preferences or {})
        raw_perm_prefs = dict(user.preferences.permission_preferences or {})
        raw_priv_prefs = dict(user.preferences.privacy_settings or {})

        prefs = UserPreferences(
            timezone=str(user.preferences.timezone),
            model_preferences=ModelPreferences(**raw_model_prefs),
            permission_preferences=PermissionPreferences(**raw_perm_prefs),
            privacy_settings=PrivacySettings(**raw_priv_prefs),
        )

    return UserProfile(
        id=str(user.id),
        email=str(user.email),
        full_name=str(user.full_name) if user.full_name else None,
        is_active=bool(user.is_active),
        created_at=cast(datetime, user.created_at),
        preferences=prefs,
    )


async def _record_auth_audit_event(
    db: AsyncSession,
    user_id: str,
    tool_name: str,
    inputs: dict[str, Any],
    verdict: str = "approved",
) -> None:
    """Record an immutable audit trail entry for security-sensitive auth actions."""
    audit_entry = AuditLogModel(
        user_id=user_id,
        session_id="auth_session",
        agent_name="auth_service",
        tool_name=tool_name,
        action_type="EXTERNAL_ACTION",
        risk_level="MEDIUM",
        inputs=inputs,
        outputs={"verdict": verdict},
        policy_verdict=verdict,
        duration_ms=1.0,
    )
    db.add(audit_entry)


@auth_router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new NEXUS user account",
)
async def register_user(
    req: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    email = req.email.strip().lower()
    if len(req.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long",
        )

    # Check for existing email
    stmt = select(UserModel).where(UserModel.email == email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists",
        )

    hashed_pw = hash_password(req.password)
    new_user = UserModel(
        email=email,
        hashed_password=hashed_pw,
        full_name=req.full_name.strip() if req.full_name else None,
    )
    db.add(new_user)
    await db.flush()

    # Create default user preferences
    default_prefs = UserPreferenceModel(
        user_id=new_user.id,
        timezone="UTC",
        model_preferences={
            "default_provider": "openai",
            "fast_model": "gpt-4o-mini",
            "reasoning_model": "gpt-4o",
            "temperature": 0.2,
        },
        permission_preferences={
            "auto_grant_low_risk": True,
            "require_hitl_high_risk": True,
            "session_grant_ttl_minutes": 60,
        },
        privacy_settings={
            "store_audit_payloads": True,
            "telemetry_enabled": False,
            "allow_external_rag": False,
        },
    )
    db.add(default_prefs)

    # Record security audit event
    await _record_auth_audit_event(
        db=db,
        user_id=str(new_user.id),
        tool_name="user_registered",
        inputs={"email": email, "has_full_name": bool(req.full_name)},
    )

    await db.commit()

    # Eager load preferences for response
    refreshed_stmt = (
        select(UserModel)
        .options(selectinload(UserModel.preferences))
        .where(UserModel.id == new_user.id)
    )
    user_res = await db.execute(refreshed_stmt)
    persisted_user = user_res.scalar_one()

    token = create_access_token(user_id=str(persisted_user.id), email=str(persisted_user.email))
    settings = get_settings()

    logger.info("user_registered_successfully", user_id=str(persisted_user.id), email=email)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.session_expiry_hours * 3600,
        user=_format_user_profile(persisted_user),
    )


@auth_router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate with email and password",
)
async def login_user(
    req: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    email = req.email.strip().lower()

    stmt = (
        select(UserModel)
        .options(selectinload(UserModel.preferences))
        .where(UserModel.email == email)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not verify_password(req.password, str(user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Record security audit event
    await _record_auth_audit_event(
        db=db,
        user_id=str(user.id),
        tool_name="user_login",
        inputs={"email": email},
    )
    await db.commit()

    token = create_access_token(user_id=str(user.id), email=str(user.email))
    settings = get_settings()

    logger.info("user_login_successful", user_id=str(user.id), email=email)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.session_expiry_hours * 3600,
        user=_format_user_profile(user),
    )


@auth_router.post(
    "/logout",
    summary="Log out user and emit audit event",
)
async def logout_user(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await _record_auth_audit_event(
        db=db,
        user_id=str(current_user.id),
        tool_name="user_logout",
        inputs={"email": str(current_user.email)},
    )
    await db.commit()
    logger.info("user_logout_successful", user_id=str(current_user.id))
    return {"status": "logged_out", "message": "Session invalidated successfully"}


@auth_router.get(
    "/me",
    response_model=UserProfile,
    summary="Get profile and preferences for the authenticated user",
)
async def get_my_profile(
    current_user: UserModel = Depends(get_current_user),
) -> UserProfile:
    return _format_user_profile(current_user)


@auth_router.patch(
    "/preferences",
    response_model=UserPreferences,
    summary="Update preferences for current user",
)
async def update_user_preferences(
    req: UpdatePreferencesRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserPreferences:
    stmt = select(UserPreferenceModel).where(UserPreferenceModel.user_id == current_user.id)
    result = await db.execute(stmt)
    prefs = result.scalar_one_or_none()

    if prefs is None:
        prefs = UserPreferenceModel(user_id=current_user.id)
        db.add(prefs)

    if req.timezone is not None:
        prefs.timezone = req.timezone

    if req.model_preferences is not None:
        current_model = dict(prefs.model_preferences or {})
        current_model.update(req.model_preferences)
        prefs.model_preferences = current_model

    if req.permission_preferences is not None:
        current_perm = dict(prefs.permission_preferences or {})
        current_perm.update(req.permission_preferences)
        prefs.permission_preferences = current_perm

    if req.privacy_settings is not None:
        current_priv = dict(prefs.privacy_settings or {})
        current_priv.update(req.privacy_settings)
        prefs.privacy_settings = current_priv

    prefs.updated_at = datetime.now(UTC)

    # Record audit log
    await _record_auth_audit_event(
        db=db,
        user_id=str(current_user.id),
        tool_name="user_preferences_updated",
        inputs=req.model_dump(exclude_unset=True),
    )

    await db.commit()
    await db.refresh(prefs)

    raw_model = dict(prefs.model_preferences or {})
    raw_perm = dict(prefs.permission_preferences or {})
    raw_priv = dict(prefs.privacy_settings or {})

    return UserPreferences(
        timezone=str(prefs.timezone),
        model_preferences=ModelPreferences(**raw_model),
        permission_preferences=PermissionPreferences(**raw_perm),
        privacy_settings=PrivacySettings(**raw_priv),
    )
