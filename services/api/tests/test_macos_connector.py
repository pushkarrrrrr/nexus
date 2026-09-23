"""Comprehensive Unit and Integration Tests for Native macOS Application Control.

Tests TCC permission checking, JXA subprocess execution, CoreGraphics synthetic events,
window capture, ToolRegistry reflection, Policy Engine safeguards, and FastAPI endpoints.
"""

import base64
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from packages.shared.nexus_shared.integrations.macos import (
    MacOSCaptureWindowTool,
    MacOSClickElementTool,
    MacOSConnector,
    MacOSFocusAppTool,
    MacOSInspectUITool,
    MacOSListRunningAppsTool,
    MacOSSendShortcutTool,
    MacOSTypeTextTool,
    check_macos_permissions,
)
from packages.shared.nexus_shared.integrations.macos import (
    engine as macos_engine,
)
from packages.shared.nexus_shared.models import ApprovalRequestModel, UserPermissionModel
from packages.shared.nexus_shared.policy import PolicyEngine
from packages.shared.nexus_shared.tools import get_tool_registry
from services.api.nexus_api.database import get_session_factory, init_database
from services.api.nexus_api.main import app


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_database()


def random_email() -> str:
    return f"macos_test_{uuid.uuid4().hex[:8]}@example.com"


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
                "full_name": "macOS Control Tester",
            },
        )
        assert reg.status_code == 201, reg.text
        token = reg.json()["access_token"]
        user_id = reg.json()["user"]["id"]
        return {"token": token, "user_id": user_id, "email": email}


# =============================================================================
# 1. TCC Permission Verification Tests
# =============================================================================
def test_check_macos_permissions_granted():
    with (
        patch(
            "packages.shared.nexus_shared.integrations.macos.permissions._check_accessibility_trusted",
            return_value=True,
        ),
        patch(
            "packages.shared.nexus_shared.integrations.macos.permissions._check_screen_capture_allowed",
            return_value=True,
        ),
        patch("platform.system", return_value="Darwin"),
    ):
        res = check_macos_permissions()
        assert res["is_macos"] is True
        assert res["accessibility_trusted"] is True
        assert res["screen_capture_allowed"] is True
        assert res["all_permissions_granted"] is True
        assert "Privacy_Accessibility" in res["settings_urls"]["accessibility"]
        assert "Privacy_ScreenCapture" in res["settings_urls"]["screen_capture"]
        assert res["diagnostics"]["accessibility"] == "Granted"
        assert res["diagnostics"]["screen_capture"] == "Granted"


def test_check_macos_permissions_missing():
    with (
        patch(
            "packages.shared.nexus_shared.integrations.macos.permissions._check_accessibility_trusted",
            return_value=False,
        ),
        patch(
            "packages.shared.nexus_shared.integrations.macos.permissions._check_screen_capture_allowed",
            return_value=False,
        ),
        patch("platform.system", return_value="Darwin"),
    ):
        res = check_macos_permissions()
        assert res["is_macos"] is True
        assert res["accessibility_trusted"] is False
        assert res["screen_capture_allowed"] is False
        assert res["all_permissions_granted"] is False
        assert "Missing" in res["diagnostics"]["accessibility"]
        assert "Missing" in res["diagnostics"]["screen_capture"]


# =============================================================================
# 2. JXA Engine Runner Tests
# =============================================================================
@pytest.mark.asyncio
async def test_run_jxa_success():
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b'{"success": true, "count": 3}', b""))

    with (
        patch("platform.system", return_value="Darwin"),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        res = await macos_engine.run_jxa("console.log('hello')")
        assert res == {"success": True, "count": 3}


@pytest.mark.asyncio
async def test_run_jxa_timeout():
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(side_effect=TimeoutError())

    with (
        patch("platform.system", return_value="Darwin"),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        pytest.raises(TimeoutError, match="timed out"),
    ):
        await macos_engine.run_jxa("while(true){}", timeout=0.1)


@pytest.mark.asyncio
async def test_jxa_list_applications():
    mock_data = [
        {"app_name": "Finder", "bundle_id": "com.apple.finder", "pid": 100, "is_frontmost": True},
        {"app_name": "Safari", "bundle_id": "com.apple.Safari", "pid": 200, "is_frontmost": False},
    ]
    with patch(
        "packages.shared.nexus_shared.integrations.macos.engine.run_jxa", return_value=mock_data
    ):
        apps = await macos_engine.list_applications()
        assert len(apps) == 2
        assert apps[0]["app_name"] == "Finder"
        assert apps[0]["is_frontmost"] is True


@pytest.mark.asyncio
async def test_jxa_focus_application():
    with patch(
        "packages.shared.nexus_shared.integrations.macos.engine.run_jxa",
        return_value={"success": True},
    ):
        ok = await macos_engine.focus_application("Safari")
        assert ok is True

    with (
        patch(
            "packages.shared.nexus_shared.integrations.macos.engine.run_jxa",
            return_value={"success": False, "error": "App not found"},
        ),
        pytest.raises(RuntimeError, match="App not found"),
    ):
        await macos_engine.focus_application("NonExistentApp")


@pytest.mark.asyncio
async def test_jxa_inspect_element_tree():
    mock_tree = {
        "app_name": "Calculator",
        "pid": 300,
        "window_count": 1,
        "tree": [
            {
                "role": "AXWindow",
                "title": "Calculator",
                "children": [
                    {"role": "AXButton", "title": "1", "children": []},
                    {"role": "AXButton", "title": "+", "children": []},
                ],
            }
        ],
    }
    with patch(
        "packages.shared.nexus_shared.integrations.macos.engine.run_jxa", return_value=mock_tree
    ):
        tree = await macos_engine.inspect_element_tree("Calculator", max_depth=2)
        assert tree["app_name"] == "Calculator"
        assert tree["window_count"] == 1
        assert len(tree["tree"]) == 1


@pytest.mark.asyncio
async def test_jxa_ax_click_and_set_value():
    with patch(
        "packages.shared.nexus_shared.integrations.macos.engine.run_jxa",
        return_value={"success": True},
    ):
        click_ok = await macos_engine.ax_click_element("Calculator", "AXButton", "1")
        assert click_ok is True

        type_ok = await macos_engine.ax_set_value("Notes", "Test Note Content", submit_key="enter")
        assert type_ok is True


# =============================================================================
# 3. CoreGraphics / Quartz Synthetic Input Tests
# =============================================================================
def test_quartz_mouse_click():
    mock_cg = MagicMock()
    mock_cf = MagicMock()
    mock_cg.CGEventCreateMouseEvent.return_value = 12345
    mock_cg.CGEventPost.return_value = None

    with patch(
        "packages.shared.nexus_shared.integrations.macos.engine._load_macos_frameworks",
        return_value=(mock_cg, mock_cf),
    ):
        ok = macos_engine.post_mouse_click(100.0, 200.0, button="left")
        assert ok is True
        assert mock_cg.CGEventCreateMouseEvent.call_count == 2
        assert mock_cg.CGEventPost.call_count == 2


def test_quartz_keyboard_string():
    mock_cg = MagicMock()
    mock_cf = MagicMock()
    mock_cg.CGEventCreateKeyboardEvent.return_value = 54321

    with patch(
        "packages.shared.nexus_shared.integrations.macos.engine._load_macos_frameworks",
        return_value=(mock_cg, mock_cf),
    ):
        ok = macos_engine.post_keyboard_string("hello", submit_key="return")
        assert ok is True
        assert mock_cg.CGEventKeyboardSetUnicodeString.called
        assert mock_cg.CGEventPost.called


def test_quartz_shortcut():
    mock_cg = MagicMock()
    mock_cf = MagicMock()
    mock_cg.CGEventCreateKeyboardEvent.return_value = 99999

    with patch(
        "packages.shared.nexus_shared.integrations.macos.engine._load_macos_frameworks",
        return_value=(mock_cg, mock_cf),
    ):
        ok = macos_engine.post_shortcut("n", ["cmd", "shift"])
        assert ok is True
        assert mock_cg.CGEventSetFlags.called
        # Check that command (0x100000) and shift (0x20000) flags were set
        flags_arg = mock_cg.CGEventSetFlags.call_args[0][1]
        assert flags_arg & macos_engine.kCGEventFlagMaskCommand
        assert flags_arg & macos_engine.kCGEventFlagMaskShift


# =============================================================================
# 4. Window Capture Tests
# =============================================================================
@pytest.mark.asyncio
async def test_capture_window_image(tmp_path):
    # Create valid 1x1 PNG sample bytes
    # PNG signature + minimal IHDR
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x64\x00\x00\x00\x32\x08\x06\x00\x00\x00"
        b"\x70\xe0\x5f\x43"
    )

    mock_proc = MagicMock()
    mock_proc.returncode = 0

    async def mock_communicate():
        return b"", b""

    mock_proc.communicate = mock_communicate

    # Intercept tempfile creation to write real dummy png
    import tempfile

    orig_named_temp = tempfile.NamedTemporaryFile

    def fake_temp(*args, **kwargs):
        f = orig_named_temp(*args, **kwargs)
        with open(f.name, "wb") as writer:
            writer.write(png_bytes)
        return f

    with (
        patch("platform.system", return_value="Darwin"),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        patch("tempfile.NamedTemporaryFile", side_effect=fake_temp),
    ):
        res = await macos_engine.capture_window_image("Antigravity IDE", window_id=256)
        assert res["app_name"] == "Antigravity IDE"
        assert res["window_id"] == 256
        assert res["format"] == "png"
        assert res["width"] == 100
        assert res["height"] == 50
        assert res["size_bytes"] > 0
        assert base64.b64decode(res["data_base64"]).startswith(b"\x89PNG")


# =============================================================================
# 5. Native macOS Tools Execution Tests
# =============================================================================
@pytest.mark.asyncio
async def test_macos_tools_execution():
    user_id = "test_user"

    # 1. list_running_apps
    list_tool = MacOSListRunningAppsTool()
    with patch(
        "packages.shared.nexus_shared.integrations.macos.engine.list_applications",
        return_value=[
            {
                "app_name": "Slack",
                "bundle_id": "com.tinyspeck.slackmacgap",
                "pid": 501,
                "is_frontmost": True,
            },
            {
                "app_name": "Spotify",
                "bundle_id": "com.spotify.client",
                "pid": 502,
                "is_frontmost": False,
            },
        ],
    ):
        res = await list_tool.execute(user_id=user_id, params={"filter_name": "sla"})
        assert res.success is True
        assert res.output.count == 1
        assert res.output.apps[0].app_name == "Slack"

    # 2. focus_app
    focus_tool = MacOSFocusAppTool()
    with patch(
        "packages.shared.nexus_shared.integrations.macos.engine.focus_application",
        return_value=True,
    ):
        res = await focus_tool.execute(user_id=user_id, params={"app_name": "Slack"})
        assert res.success is True
        assert "activated" in res.output.message

    # 3. inspect_ui
    inspect_tool = MacOSInspectUITool()
    with patch(
        "packages.shared.nexus_shared.integrations.macos.engine.inspect_element_tree",
        return_value={"app_name": "Slack", "pid": 501, "window_count": 1, "tree": []},
    ):
        res = await inspect_tool.execute(
            user_id=user_id, params={"app_name": "Slack", "max_depth": 2}
        )
        assert res.success is True
        assert res.output.app_name == "Slack"

    # 4. capture_window
    capture_tool = MacOSCaptureWindowTool()
    with patch(
        "packages.shared.nexus_shared.integrations.macos.engine.capture_window_image",
        return_value={
            "app_name": "Slack",
            "window_id": 12,
            "format": "png",
            "width": 800,
            "height": 600,
            "size_bytes": 1024,
            "data_base64": "fake_b64",
        },
    ):
        res = await capture_tool.execute(user_id=user_id, params={"app_name": "Slack"})
        assert res.success is True
        assert res.output.width == 800

    # 5. click_element (HIGH risk action execution)
    click_tool = MacOSClickElementTool()
    with patch(
        "packages.shared.nexus_shared.integrations.macos.engine.ax_click_element", return_value=True
    ):
        res = await click_tool.execute(
            user_id=user_id,
            params={"app_name": "Slack", "role": "AXButton", "title": "Send"},
        )
        assert res.success is True
        assert "Clicked element" in res.output.message

    # 6. type_text (HIGH risk action execution)
    type_tool = MacOSTypeTextTool()
    with patch(
        "packages.shared.nexus_shared.integrations.macos.engine.ax_set_value", return_value=True
    ):
        res = await type_tool.execute(
            user_id=user_id,
            params={
                "app_name": "Slack",
                "text": "Deploying NEXUS Phase 13!",
                "submit_key": "enter",
            },
        )
        assert res.success is True
        assert res.output.typed_length > 0

    # 7. send_shortcut (HIGH risk action execution)
    shortcut_tool = MacOSSendShortcutTool()
    with (
        patch(
            "packages.shared.nexus_shared.integrations.macos.engine.focus_application",
            return_value=True,
        ),
        patch(
            "packages.shared.nexus_shared.integrations.macos.engine.post_shortcut",
            return_value=True,
        ),
    ):
        res = await shortcut_tool.execute(
            user_id=user_id,
            params={"app_name": "Slack", "key": "k", "modifiers": ["cmd"]},
        )
        assert res.success is True
        assert "cmd+k" in res.output.message


# =============================================================================
# 6. Policy Engine Strict Risk Gating & Approval Request Tests
# =============================================================================
@pytest.mark.asyncio
async def test_policy_engine_strictly_gates_mutating_macos_actions(auth_user):
    user_id = auth_user["user_id"]
    policy_engine = PolicyEngine()
    session_factory = get_session_factory()

    async with session_factory() as db:
        # 1. macos.click_element without grant must return REQUIRES_APPROVAL with HIGH risk
        click_decision = await policy_engine.evaluate_action(
            db=db,
            user_id=user_id,
            capability_name="macos.click_element",
            resource_target="app:System Preferences",
            params={"app_name": "System Preferences", "role": "AXButton", "title": "Save"},
            tool_name="macos.click_element",
        )
        assert click_decision.verdict == "REQUIRES_APPROVAL"
        assert click_decision.risk_level == "HIGH"
        assert click_decision.approval_id is not None

        # Verify ApprovalRequestModel was written to database
        appr = await db.get(ApprovalRequestModel, click_decision.approval_id)
        assert appr is not None
        assert appr.capability_name == "macos.click_element"
        assert appr.risk_level == "HIGH"
        assert appr.status == "PENDING"
        assert appr.action_category == "SYSTEM_CONTROL"
        assert appr.parameters["app_name"] == "System Preferences"

        # 2. macos.type_text without grant must return REQUIRES_APPROVAL with HIGH risk
        type_decision = await policy_engine.evaluate_action(
            db=db,
            user_id=user_id,
            capability_name="macos.type_text",
            resource_target="app:Terminal",
            params={"app_name": "Terminal", "text": "sudo rm -rf /"},
            tool_name="macos.type_text",
        )
        assert type_decision.verdict == "REQUIRES_APPROVAL"
        assert type_decision.risk_level == "HIGH"

        # 3. macos.send_shortcut without grant must return REQUIRES_APPROVAL with HIGH risk
        shortcut_decision = await policy_engine.evaluate_action(
            db=db,
            user_id=user_id,
            capability_name="macos.send_shortcut",
            resource_target="app:Finder",
            params={"app_name": "Finder", "key": "delete", "modifiers": ["cmd"]},
            tool_name="macos.send_shortcut",
        )
        assert shortcut_decision.verdict == "REQUIRES_APPROVAL"
        assert shortcut_decision.risk_level == "HIGH"

        # 4. Low risk action with standing permission grant must evaluate to ALLOWED
        perm = UserPermissionModel(
            user_id=user_id,
            capability_name="macos.list_running_apps",
            resource_pattern="*",
            scope="SESSION",
        )
        db.add(perm)
        await db.commit()

        read_decision = await policy_engine.evaluate_action(
            db=db,
            user_id=user_id,
            capability_name="macos.list_running_apps",
            resource_target="*",
            params={},
            tool_name="macos.list_running_apps",
        )
        assert read_decision.verdict == "ALLOWED"
        assert read_decision.risk_level == "LOW"


# =============================================================================
# 7. ToolRegistry Reflection & Connector Lifecycle Tests
# =============================================================================
def test_all_macos_tools_registered():
    registry = get_tool_registry()
    expected_macos_tools = [
        "macos.list_running_apps",
        "macos.focus_app",
        "macos.inspect_ui",
        "macos.capture_window",
        "macos.click_element",
        "macos.type_text",
        "macos.send_shortcut",
    ]
    for tool_name in expected_macos_tools:
        tool = registry.get(tool_name)
        assert tool is not None, f"Tool '{tool_name}' missing from ToolRegistry"
        assert tool.name == tool_name


@pytest.mark.asyncio
async def test_macos_connector_lifecycle():
    connector = MacOSConnector()
    assert connector.provider == "macos"

    with patch(
        "packages.shared.nexus_shared.integrations.macos.connector.check_macos_permissions"
    ) as mock_perms:
        mock_perms.return_value = {
            "accessibility_trusted": True,
            "screen_capture_allowed": True,
            "all_permissions_granted": True,
        }
        with patch("platform.system", return_value="Darwin"):
            ok = await connector.connect("user_123", {})
            assert ok is True

            health = await connector.health_check("user_123")
            assert health["provider"] == "macos"
            assert health["status"] == "healthy"
            assert health["tool_count"] == 7

            disc = await connector.disconnect("user_123")
            assert disc is True

            tools = connector.register_tools()
            assert len(tools) == 7


# =============================================================================
# 8. FastAPI Endpoints Tests
# =============================================================================
@pytest.mark.asyncio
async def test_api_macos_endpoints(auth_user):
    token = auth_user["token"]
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test GET /api/v1/integrations/macos/permissions
        with patch(
            "services.api.nexus_api.routes.v1.integrations.check_macos_permissions",
            return_value={
                "is_macos": True,
                "platform": "Darwin",
                "executable_path": "/usr/bin/python3",
                "accessibility_trusted": True,
                "screen_capture_allowed": True,
                "all_permissions_granted": True,
                "settings_urls": {
                    "accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
                    "screen_capture": "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
                },
                "diagnostics": {"accessibility": "Granted", "screen_capture": "Granted"},
            },
        ):
            resp = await client.get("/api/v1/integrations/macos/permissions", headers=headers)
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["is_macos"] is True
            assert data["accessibility_trusted"] is True
            assert "settings_urls" in data

        # Test GET /api/v1/integrations/macos/apps
        with patch(
            "services.api.nexus_api.routes.v1.integrations.macos_engine.list_applications",
            return_value=[
                {
                    "app_name": "Finder",
                    "bundle_id": "com.apple.finder",
                    "pid": 100,
                    "is_frontmost": True,
                }
            ],
        ):
            resp = await client.get("/api/v1/integrations/macos/apps", headers=headers)
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["count"] == 1
            assert data["apps"][0]["app_name"] == "Finder"

        # Test POST /api/v1/integrations/macos/connect
        resp = await client.post("/api/v1/integrations/macos/connect", json={}, headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["provider"] == "macos"
        assert resp.json()["status"] == "ACTIVE"

        # Test GET /api/v1/integrations/macos/health
        resp = await client.get("/api/v1/integrations/macos/health", headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["provider"] == "macos"

        # Test POST /api/v1/integrations/macos/disconnect
        resp = await client.post("/api/v1/integrations/macos/disconnect", headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["disconnected"] is True
