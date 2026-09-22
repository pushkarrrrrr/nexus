"""FastAPI API Endpoints for External Integrations & Browser Automation."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.integrations import (
    BrowserConnector,
    GitHubConnector,
    GoogleWorkspaceConnector,
    decrypt_credentials,
    encrypt_credentials,
    get_browser_session_manager,
    set_user_github_token,
    set_user_google_token,
)
from packages.shared.nexus_shared.integrations.macos import (
    MacOSConnector,
    check_macos_permissions,
)
from packages.shared.nexus_shared.integrations.macos import (
    engine as macos_engine,
)
from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import ExternalIntegrationModel, UserModel
from services.api.nexus_api.auth.dependencies import get_current_user
from services.api.nexus_api.database import get_db

logger = get_logger("nexus.routes.integrations")

integrations_router = APIRouter(prefix="/integrations", tags=["Integrations"])

KNOWN_PROVIDERS = ["browser", "github", "google", "macos"]
browser_connector = BrowserConnector()
github_connector = GitHubConnector()
google_connector = GoogleWorkspaceConnector()
macos_connector = MacOSConnector()


# -----------------------------------------------------------------------------
# Request & Response Schemas
# -----------------------------------------------------------------------------
class ConnectIntegrationRequest(BaseModel):
    token: str | None = Field(default=None, description="API token, PAT, or OAuth access token.")
    credentials: dict[str, Any] | None = Field(
        default=None, description="Optional raw credential payload."
    )
    metadata: dict[str, Any] | None = Field(
        default=None, description="Optional provider configuration metadata."
    )


class LoginSessionRequest(BaseModel):
    url: str = Field(..., description="Authentication target URL to launch in visible browser.")
    timeout_seconds: int = Field(
        default=180, description="Visible window timeout for manual QR/2FA login."
    )


class IntegrationStatusResponse(BaseModel):
    provider: str
    status: str
    is_enabled: bool
    last_sync_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# Route Handlers
# -----------------------------------------------------------------------------
@integrations_router.get("", response_model=list[IntegrationStatusResponse])
async def list_integrations(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[IntegrationStatusResponse]:
    """List all integrations and their connection statuses for the current user."""
    stmt = select(ExternalIntegrationModel).where(
        ExternalIntegrationModel.user_id == current_user.id
    )
    result = await db.execute(stmt)
    existing = {item.provider: item for item in result.scalars().all()}

    responses: list[IntegrationStatusResponse] = []
    for provider in KNOWN_PROVIDERS:
        if provider in existing:
            item = existing[provider]
            responses.append(
                IntegrationStatusResponse(
                    provider=item.provider,
                    status=item.status,
                    is_enabled=item.is_enabled,
                    last_sync_at=item.last_sync_at,
                    metadata=item.config or {},
                )
            )
        else:
            # Default unconfigured provider record
            responses.append(
                IntegrationStatusResponse(
                    provider=provider,
                    status="DISCONNECTED",
                    is_enabled=False,
                    last_sync_at=None,
                    metadata={},
                )
            )

    return responses


@integrations_router.post("/{provider}/connect", response_model=IntegrationStatusResponse)
async def connect_integration(
    provider: str,
    body: ConnectIntegrationRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IntegrationStatusResponse:
    """Store encrypted credentials and connect an external provider for the user."""
    provider_lower = provider.lower()
    if provider_lower not in KNOWN_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown integration provider '{provider}'. Known: {KNOWN_PROVIDERS}",
        )

    # Build credential payload
    creds = body.credentials or {}
    if body.token:
        creds["token"] = body.token

    if provider_lower in ("github", "google") and not creds.get("token"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{provider}' requires an authentication token.",
        )

    encrypted_b64 = encrypt_credentials(creds)

    # Update in-memory connector store
    if provider_lower == "github":
        set_user_github_token(current_user.id, creds.get("token", ""))
    elif provider_lower == "google":
        set_user_google_token(current_user.id, creds.get("token", ""))
    elif provider_lower == "browser":
        await browser_connector.connect(current_user.id, creds, body.metadata)
    elif provider_lower == "macos":
        await macos_connector.connect(current_user.id, creds, body.metadata)

    # Persist in database
    stmt = select(ExternalIntegrationModel).where(
        ExternalIntegrationModel.user_id == current_user.id,
        ExternalIntegrationModel.provider == provider_lower,
    )
    result = await db.execute(stmt)
    integration = result.scalar_one_or_none()

    now = datetime.now(UTC)
    if integration is None:
        integration = ExternalIntegrationModel(
            user_id=current_user.id,
            provider=provider_lower,
            is_enabled=True,
            credentials_encrypted=encrypted_b64,
            config=body.metadata or {},
            status="ACTIVE",
            last_sync_at=now,
        )
        db.add(integration)
    else:
        integration.credentials_encrypted = encrypted_b64
        integration.is_enabled = True
        integration.status = "ACTIVE"
        integration.config = body.metadata or integration.config or {}
        integration.last_sync_at = now

    await db.commit()
    await db.refresh(integration)

    return IntegrationStatusResponse(
        provider=integration.provider,
        status=integration.status,
        is_enabled=integration.is_enabled,
        last_sync_at=integration.last_sync_at,
        metadata=integration.config,
    )


@integrations_router.post("/{provider}/disconnect")
async def disconnect_integration(
    provider: str,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Disconnect and purge credentials for an external provider."""
    provider_lower = provider.lower()
    if provider_lower not in KNOWN_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown integration provider '{provider}'.",
        )

    if provider_lower == "github":
        await github_connector.disconnect(current_user.id)
    elif provider_lower == "google":
        await google_connector.disconnect(current_user.id)
    elif provider_lower == "browser":
        await browser_connector.disconnect(current_user.id)
    elif provider_lower == "macos":
        await macos_connector.disconnect(current_user.id)

    stmt = select(ExternalIntegrationModel).where(
        ExternalIntegrationModel.user_id == current_user.id,
        ExternalIntegrationModel.provider == provider_lower,
    )
    result = await db.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration:
        integration.status = "DISCONNECTED"
        integration.is_enabled = False
        integration.credentials_encrypted = None
        await db.commit()

    return {"status": "success", "provider": provider_lower, "disconnected": True}


@integrations_router.get("/{provider}/health")
async def integration_health(
    provider: str,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Check connection health and validity for an integration provider."""
    provider_lower = provider.lower()
    if provider_lower not in KNOWN_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown integration provider '{provider}'.",
        )

    # Hydrate in-memory token from encrypted DB store if needed
    stmt = select(ExternalIntegrationModel).where(
        ExternalIntegrationModel.user_id == current_user.id,
        ExternalIntegrationModel.provider == provider_lower,
    )
    result = await db.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration and integration.credentials_encrypted:
        try:
            creds = decrypt_credentials(integration.credentials_encrypted)
            if isinstance(creds, dict) and "token" in creds:
                if provider_lower == "github":
                    set_user_github_token(current_user.id, creds["token"])
                elif provider_lower == "google":
                    set_user_google_token(current_user.id, creds["token"])
        except (ValueError, KeyError, TypeError) as e:
            logger.debug("failed_to_decrypt_stored_credentials", error=str(e))

    if provider_lower == "browser":
        return await browser_connector.health_check(current_user.id)
    if provider_lower == "github":
        return await github_connector.health_check(current_user.id)
    if provider_lower == "google":
        return await google_connector.health_check(current_user.id)
    if provider_lower == "macos":
        return await macos_connector.health_check(current_user.id)

    return {"provider": provider_lower, "status": "unknown"}


@integrations_router.post("/browser/login-session")
async def launch_browser_login_session(
    body: LoginSessionRequest,
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Launch a visible persistent browser window for manual 2FA/QR code authentication."""
    session_manager = get_browser_session_manager()
    from packages.shared.nexus_shared.integrations.browser.ssrf import validate_url_safe

    safe_url = validate_url_safe(body.url)
    page = await session_manager.get_active_page(current_user.id, headless=False)
    await page.goto(safe_url, timeout=30000, wait_until="domcontentloaded")

    return {
        "status": "launched",
        "url": safe_url,
        "message": "Interactive browser window spawned. Complete manual login and close when finished.",
    }


# -----------------------------------------------------------------------------
# Native macOS Application Control Endpoints
# -----------------------------------------------------------------------------
@integrations_router.get("/macos/apps")
async def list_macos_apps(
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """List active desktop GUI applications running on macOS."""
    try:
        apps = await macos_engine.list_applications()
        return {"apps": apps, "count": len(apps)}
    except (RuntimeError, OSError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list running applications: {e}",
        ) from e


@integrations_router.get("/macos/permissions")
async def get_macos_permissions(
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Inspect macOS TCC permission state (Accessibility, Screen Recording) with settings deep links."""
    return check_macos_permissions()

