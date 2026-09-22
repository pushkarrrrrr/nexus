"""Comprehensive Unit and Integration Tests for Phase 13 External Integrations.

Tests AES-256-GCM crypto, SSRF validation, Playwright BrowserSessionManager,
GitHub connector, Google Workspace connector, Policy Engine gating, and FastAPI routes.
"""

import os
import stat
import uuid
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from packages.shared.nexus_shared.integrations import (
    BrowserClickTool,
    BrowserGetSnapshotTool,
    BrowserNavigateTool,
    BrowserSessionManager,
    BrowserTypeTool,
    GitHubCreateIssueTool,
    GitHubListIssuesTool,
    GoogleListCalendarEventsTool,
    GoogleSendEmailTool,
    SSRFSecurityViolation,
    decrypt_credentials,
    encrypt_credentials,
    set_user_github_token,
    set_user_google_token,
    validate_url_safe,
)
from packages.shared.nexus_shared.models import (
    ApprovalRequestModel,
)
from packages.shared.nexus_shared.policy import PolicyEngine
from packages.shared.nexus_shared.policy.registry import get_capability_registry
from packages.shared.nexus_shared.tools import get_tool_registry
from services.api.nexus_api.database import get_session_factory, init_database
from services.api.nexus_api.main import app


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_database()


def random_email() -> str:
    return f"integration_test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
async def auth_user():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = random_email()
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Password123!",
                "full_name": "Integration Test User",
            },
        )
        assert reg.status_code == 201, reg.text
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "Password123!"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        user_id = reg.json()["user"]["id"]
        yield {
            "client": client,
            "token": token,
            "user_id": user_id,
            "headers": {"Authorization": f"Bearer {token}"},
        }


# =============================================================================
# 1. AES-256-GCM Token Encryption Tests
# =============================================================================
def test_crypto_encryption_roundtrip_dict():
    payload = {"token": "ghp_secure_token_1234567890", "scopes": ["repo", "user"]}
    encrypted_b64 = encrypt_credentials(payload)
    assert isinstance(encrypted_b64, str)
    assert encrypted_b64 != str(payload)

    decrypted = decrypt_credentials(encrypted_b64)
    assert decrypted == payload
    assert decrypted["token"] == "ghp_secure_token_1234567890"


def test_crypto_encryption_roundtrip_string():
    raw = "ya29.google_bearer_token_string_example"
    encrypted_b64 = encrypt_credentials(raw)
    decrypted = decrypt_credentials(encrypted_b64)
    assert decrypted == raw


def test_crypto_invalid_payload_error():
    with pytest.raises(ValueError):
        decrypt_credentials("invalid_short_base64")


# =============================================================================
# 2. SSRF Validation Hardening Tests
# =============================================================================
def test_ssrf_allows_valid_public_urls():
    assert validate_url_safe("https://example.com") == "https://example.com"
    assert validate_url_safe("https://github.com/login") == "https://github.com/login"


def test_ssrf_rejects_loopback():
    with pytest.raises(SSRFSecurityViolation):
        validate_url_safe("http://127.0.0.1:8000/admin")
    with pytest.raises(SSRFSecurityViolation):
        validate_url_safe("http://localhost:3000")


def test_ssrf_rejects_rfc1918_private_subnets():
    with pytest.raises(SSRFSecurityViolation):
        validate_url_safe("http://10.0.0.1/internal")
    with pytest.raises(SSRFSecurityViolation):
        validate_url_safe("http://192.168.1.1/router")
    with pytest.raises(SSRFSecurityViolation):
        validate_url_safe("http://172.16.0.5/api")


def test_ssrf_rejects_cloud_metadata():
    with pytest.raises(SSRFSecurityViolation):
        validate_url_safe("http://169.254.169.254/latest/meta-data")


def test_ssrf_rejects_forbidden_schemes():
    with pytest.raises(SSRFSecurityViolation):
        validate_url_safe("file:///etc/passwd")
    with pytest.raises(SSRFSecurityViolation):
        validate_url_safe("ftp://ftp.example.com")


# =============================================================================
# 3. Playwright BrowserSessionManager Tests
# =============================================================================
def test_browser_profile_permissions_0700():
    with TemporaryDirectory() as tmpdir:
        manager = BrowserSessionManager(base_profile_dir=tmpdir)
        user_dir = manager.get_user_profile_dir("test_user_posix_123")
        assert user_dir.exists()
        file_stat = os.stat(user_dir)
        mode = stat.S_IMODE(file_stat.st_mode)
        assert mode == 0o700


@pytest.mark.asyncio
async def test_browser_session_idle_reaper():
    with TemporaryDirectory() as tmpdir:
        manager = BrowserSessionManager(base_profile_dir=tmpdir)
        mock_context = AsyncMock()
        mock_play = AsyncMock()

        # Insert a simulated session that is 700 seconds old (> 600 default)
        from packages.shared.nexus_shared.integrations.browser.session import BrowserSessionRecord

        record = BrowserSessionRecord(context=mock_context, play=mock_play, headless=True)
        record.last_active = 0.0  # long ago
        manager._sessions["user_idle_test"] = record

        reaped = await manager.reap_idle_contexts(timeout_seconds=600.0)
        assert reaped == 1
        assert "user_idle_test" not in manager._sessions
        mock_context.close.assert_awaited_once()
        mock_play.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_browser_session_manager_get_context_mock():
    with TemporaryDirectory() as tmpdir:
        manager = BrowserSessionManager(base_profile_dir=tmpdir)

        mock_page = AsyncMock()
        mock_page.is_closed.return_value = False
        mock_context = AsyncMock()
        mock_context.pages = [mock_page]
        mock_chromium = AsyncMock()
        mock_chromium.launch_persistent_context.return_value = mock_context
        mock_play = AsyncMock()
        mock_play.chromium = mock_chromium

        with patch("packages.shared.nexus_shared.integrations.browser.session.async_playwright") as mock_pw_factory:
            pw_cm = AsyncMock()
            pw_cm.start.return_value = mock_play
            mock_pw_factory.return_value = pw_cm

            page = await manager.get_active_page("user_pw_test", headless=True)
            assert page == mock_page
            mock_chromium.launch_persistent_context.assert_awaited_once()

            await manager.close_session("user_pw_test")
            mock_context.close.assert_awaited_once()


# =============================================================================
# 4. Browser Tools Execution Tests
# =============================================================================
@pytest.mark.asyncio
async def test_browser_navigate_and_snapshot_tools():
    mock_session_mgr = MagicMock()
    mock_page = AsyncMock()
    mock_page.title.return_value = "Example Domain"
    mock_page.url = "https://example.com"
    mock_page.inner_text.return_value = "Example Domain Content Body"
    mock_page.screenshot.return_value = b"fake_screenshot_png_bytes"
    mock_session_mgr.get_active_page = AsyncMock(return_value=mock_page)

    # Test navigate tool
    nav_tool = BrowserNavigateTool(session_manager=mock_session_mgr)
    nav_res = await nav_tool.run("test_user", nav_tool.input_schema(url="https://example.com"))
    assert nav_res.url == "https://example.com"
    assert nav_res.title == "Example Domain"

    # Test snapshot tool
    snap_tool = BrowserGetSnapshotTool(session_manager=mock_session_mgr)
    snap_res = await snap_tool.run(
        "test_user",
        snap_tool.input_schema(extract_text=True, capture_screenshot=True),
    )
    assert snap_res.title == "Example Domain"
    assert snap_res.text_content is not None
    assert "Example Domain Content Body" in snap_res.text_content
    assert snap_res.screenshot_base64 is not None


@pytest.mark.asyncio
async def test_browser_click_and_type_tools():
    mock_session_mgr = MagicMock()
    mock_page = AsyncMock()
    mock_page.url = "https://example.com/submitted"
    mock_session_mgr.get_active_page = AsyncMock(return_value=mock_page)

    click_tool = BrowserClickTool(session_manager=mock_session_mgr)
    assert click_tool.default_risk_level == "HIGH"
    assert click_tool.required_capability == "browser.click"

    click_res = await click_tool.run("test_user", click_tool.input_schema(selector="#submit-button"))
    assert click_res.success is True
    mock_page.click.assert_awaited_once_with("#submit-button", timeout=10000)

    type_tool = BrowserTypeTool(session_manager=mock_session_mgr)
    assert type_tool.default_risk_level == "HIGH"
    type_res = await type_tool.run(
        "test_user",
        type_tool.input_schema(selector="#username", text="alice", submit=True),
    )
    assert type_res.success is True
    mock_page.fill.assert_awaited_once_with("#username", "alice", timeout=10000)
    mock_page.press.assert_awaited_once_with("#username", "Enter")


# =============================================================================
# 5. GitHub Connector & Tools Tests
# =============================================================================
@pytest.mark.asyncio
async def test_github_tools_with_mock_client():
    user_id = "test_gh_user_001"
    set_user_github_token(user_id, "mock_gh_token_abc")

    # 1. list issues
    list_tool = GitHubListIssuesTool()
    assert list_tool.default_risk_level == "LOW"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"id": 101, "number": 1, "title": "Bug in auth", "state": "open", "html_url": "https://github.com/owner/repo/issues/1"}
    ]

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        out = await list_tool.run(user_id, list_tool.input_schema(repo="owner/repo"))
        assert len(out.issues) == 1
        assert out.issues[0]["title"] == "Bug in auth"

    # 2. create issue (HIGH RISK)
    create_tool = GitHubCreateIssueTool()
    assert create_tool.default_risk_level == "HIGH"

    mock_create_resp = MagicMock()
    mock_create_resp.status_code = 201
    mock_create_resp.json.return_value = {
        "id": 102,
        "number": 2,
        "title": "New Issue",
        "html_url": "https://github.com/owner/repo/issues/2",
    }

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_create_resp)):
        create_out = await create_tool.run(
            user_id,
            create_tool.input_schema(repo="owner/repo", title="New Issue", body="Issue details"),
        )
        assert create_out.number == 2
        assert create_out.title == "New Issue"


# =============================================================================
# 6. Google Workspace Connector & Tools Tests
# =============================================================================
@pytest.mark.asyncio
async def test_google_tools_with_mock_client():
    user_id = "test_google_user_001"
    set_user_google_token(user_id, "mock_google_oauth_token_xyz")

    # 1. list calendar events
    cal_tool = GoogleListCalendarEventsTool()
    assert cal_tool.default_risk_level == "LOW"

    mock_cal_resp = MagicMock()
    mock_cal_resp.status_code = 200
    mock_cal_resp.json.return_value = {
        "items": [
            {
                "id": "evt_1",
                "summary": "Sprint Planning",
                "start": {"dateTime": "2026-09-22T10:00:00Z"},
                "end": {"dateTime": "2026-09-22T11:00:00Z"},
                "status": "confirmed",
            }
        ]
    }

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_cal_resp)):
        cal_out = await cal_tool.run(
            user_id,
            cal_tool.input_schema(time_min="2026-09-22T00:00:00Z", time_max="2026-09-22T23:59:59Z"),
        )
        assert len(cal_out.events) == 1
        assert cal_out.events[0]["summary"] == "Sprint Planning"

    # 2. send email (HIGH RISK)
    email_tool = GoogleSendEmailTool()
    assert email_tool.default_risk_level == "HIGH"

    mock_mail_resp = MagicMock()
    mock_mail_resp.status_code = 200
    mock_mail_resp.json.return_value = {"id": "msg_999"}

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_mail_resp)):
        mail_out = await email_tool.run(
            user_id,
            email_tool.input_schema(to="user@example.com", subject="Hello NEXUS", body="Automated message"),
        )
        assert mail_out.id == "msg_999"
        assert mail_out.to == "user@example.com"


# =============================================================================
# 7. Policy Engine Risk Tiering & Gating Tests
# =============================================================================
@pytest.mark.asyncio
async def test_policy_engine_strictly_gates_high_risk_integration_actions(auth_user):
    user_id = auth_user["user_id"]
    session_factory = get_session_factory()
    policy_engine = PolicyEngine()

    # Verify mutating tools have HIGH risk in PolicyRegistry
    cap_registry = get_capability_registry()
    assert cap_registry.get_risk_level("browser.click") == "HIGH"
    assert cap_registry.get_risk_level("browser.type") == "HIGH"
    assert cap_registry.get_risk_level("github.create_issue") == "HIGH"
    assert cap_registry.get_risk_level("google.send_email") == "HIGH"

    # Verify read tools have LOW risk
    assert cap_registry.get_risk_level("browser.get_snapshot") == "LOW"
    assert cap_registry.get_risk_level("github.list_issues") == "LOW"
    assert cap_registry.get_risk_level("google.list_calendar_events") == "LOW"

    async with session_factory() as db:
        # Evaluating browser.click must result in REQUIRES_APPROVAL
        decision = await policy_engine.evaluate_action(
            db=db,
            user_id=user_id,
            capability_name="browser.click",
            resource_target="selector:#confirm-purchase-button",
            params={"selector": "#confirm-purchase-button"},
            tool_name="browser.click",
        )
        assert decision.verdict == "REQUIRES_APPROVAL"
        assert decision.risk_level == "HIGH"
        assert decision.approval_id is not None

        # Verify ApprovalRequestModel exists in DB
        appr = await db.get(ApprovalRequestModel, decision.approval_id)
        assert appr is not None
        assert appr.capability_name == "browser.click"
        assert appr.risk_level == "HIGH"
        assert appr.status == "PENDING"

        # Add permission grant for browser.get_snapshot
        from packages.shared.nexus_shared.models import UserPermissionModel

        perm = UserPermissionModel(
            user_id=user_id,
            capability_name="browser.get_snapshot",
            resource_pattern="*",
            scope="SESSION",
        )
        db.add(perm)
        await db.commit()

        # Evaluating browser.get_snapshot with standing grant must be ALLOWED
        read_decision = await policy_engine.evaluate_action(
            db=db,
            user_id=user_id,
            capability_name="browser.get_snapshot",
            resource_target="",
            params={"extract_text": True},
            tool_name="browser.get_snapshot",
        )
        assert read_decision.verdict == "ALLOWED"
        assert read_decision.risk_level == "LOW"


# =============================================================================
# 8. ToolRegistry Reflection Tests
# =============================================================================
def test_all_phase_13_tools_registered():
    registry = get_tool_registry()
    expected_tools = [
        "browser.open_login_session",
        "browser.navigate",
        "browser.get_snapshot",
        "browser.click",
        "browser.type",
        "github.list_issues",
        "github.read_file",
        "github.create_issue",
        "github.create_pr",
        "google.list_calendar_events",
        "google.create_calendar_event",
        "google.search_gmail",
        "google.send_email",
    ]
    for tool_name in expected_tools:
        tool = registry.get(tool_name)
        assert tool is not None, f"Tool '{tool_name}' missing from ToolRegistry"


# =============================================================================
# 9. FastAPI Integration Routes Tests
# =============================================================================
@pytest.mark.asyncio
async def test_api_integrations_lifecycle(auth_user):
    client = auth_user["client"]
    headers = auth_user["headers"]

    # 1. List integrations
    res = await client.get("/api/v1/integrations", headers=headers)
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 3
    providers = {i["provider"] for i in items}
    assert "browser" in providers
    assert "github" in providers
    assert "google" in providers

    # 2. Connect GitHub
    connect_res = await client.post(
        "/api/v1/integrations/github/connect",
        headers=headers,
        json={"token": "ghp_mock_token_for_api_test"},
    )
    assert connect_res.status_code == 200
    assert connect_res.json()["status"] == "ACTIVE"
    assert connect_res.json()["provider"] == "github"

    # 3. Disconnect GitHub
    disc_res = await client.post(
        "/api/v1/integrations/github/disconnect",
        headers=headers,
    )
    assert disc_res.status_code == 200
    assert disc_res.json()["disconnected"] is True

    # 4. Check Browser Health
    health_res = await client.get(
        "/api/v1/integrations/browser/health",
        headers=headers,
    )
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"
