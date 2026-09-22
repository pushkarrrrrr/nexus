"""Unit and Integration Tests for Tool System, Controlled Computer Actions, and OS Adapters."""

import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from httpx import ASGITransport, AsyncClient

from packages.shared.nexus_shared.agents.computer_agent import ComputerAgent
from packages.shared.nexus_shared.computer import MacOSAdapter
from packages.shared.nexus_shared.computer.base import (
    MAX_COMMAND_OUTPUT_BYTES,
    is_protected_directory,
)
from packages.shared.nexus_shared.models import (
    UserModel,
    UserPermissionModel,
)
from packages.shared.nexus_shared.tools import (
    ApplicationOpenTool,
    BrowserOpenUrlTool,
    FilesystemDeleteTool,
    FilesystemListDirTool,
    FilesystemMoveTool,
    FilesystemReadTool,
    FilesystemWriteTool,
    TerminalExecuteTool,
    get_tool_registry,
)
from packages.types.nexus_types.schemas import PlanStep
from services.api.nexus_api.database import get_session_factory, init_database
from services.api.nexus_api.main import app


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_database()


def random_email() -> str:
    return f"tools_test_{uuid.uuid4().hex[:8]}@example.com"


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
                "full_name": "Tool Test User",
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


@pytest.fixture
async def test_user() -> str:
    session_factory = get_session_factory()
    user_id = f"usr_{uuid.uuid4().hex[:16]}"
    async with session_factory() as session:
        user = UserModel(
            id=user_id,
            email=random_email(),
            hashed_password="test_hashed_password",
            full_name="Direct Tool User",
            is_active=True,
        )
        session.add(user)
        await session.commit()
    return user_id


async def grant_permission(
    session,
    user_id: str,
    capability_name: str,
    resource_pattern: str = "*",
    scope: str = "SESSION",
) -> UserPermissionModel:
    perm = UserPermissionModel(
        user_id=user_id,
        capability_name=capability_name,
        scope=scope,
        resource_pattern=resource_pattern,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.add(perm)
    await session.commit()
    return perm


# ==============================================================================
# 1. Tool Registry & Schema Reflection
# ==============================================================================


def test_tool_registry_registration_and_schemas():
    registry = get_tool_registry()
    tools = registry.list_tools()
    tool_names = {t.name for t in tools}

    assert "filesystem.read" in tool_names
    assert "filesystem.write" in tool_names
    assert "filesystem.move" in tool_names
    assert "filesystem.delete" in tool_names
    assert "filesystem.list_dir" in tool_names
    assert "terminal.execute" in tool_names
    assert "applications.open" in tool_names
    assert "browser.open_url" in tool_names

    schemas = registry.get_schemas_for_llm()
    assert len(schemas) >= 8
    for s in schemas:
        assert s["type"] == "function"
        assert "name" in s["function"]
        assert "description" in s["function"]
        assert "parameters" in s["function"]


# ==============================================================================
# 2. Filesystem Tools & Reversible Snapshots
# ==============================================================================


@pytest.mark.asyncio
async def test_filesystem_tools_lifecycle(test_user: str):
    session_factory = get_session_factory()
    user_id = test_user

    with TemporaryDirectory() as tmpdir:
        # Grant filesystem permissions for the test
        async with session_factory() as session:
            for cap in [
                "filesystem.read",
                "filesystem.write",
                "filesystem.modify",
                "filesystem.delete",
            ]:
                await grant_permission(session, user_id, cap, "*")

        write_tool = FilesystemWriteTool()
        read_tool = FilesystemReadTool()
        move_tool = FilesystemMoveTool()
        list_tool = FilesystemListDirTool()
        del_tool = FilesystemDeleteTool()

        test_file = Path(tmpdir) / "notes.txt"
        moved_file = Path(tmpdir) / "archived_notes.txt"

        # 1. Write file (triggers pre-snapshot)
        async with session_factory() as session:
            write_res = await write_tool.execute(
                user_id=user_id,
                params={"path": str(test_file), "content": "Hello NEXUS Tools!"},
                db=session,
            )
            assert write_res.success is True
            assert write_res.snapshot_id is not None
            assert test_file.exists()

        # 2. Read file
        async with session_factory() as session:
            read_res = await read_tool.execute(
                user_id=user_id,
                params={"path": str(test_file)},
                db=session,
            )
            assert read_res.success is True
            assert read_res.output.content == "Hello NEXUS Tools!"

        # 3. List directory
        async with session_factory() as session:
            list_res = await list_tool.execute(
                user_id=user_id,
                params={"path": tmpdir},
                db=session,
            )
            assert list_res.success is True
            assert list_res.output.total >= 1
            names = [item.name for item in list_res.output.items]
            assert "notes.txt" in names

        # 4. Move file
        async with session_factory() as session:
            move_res = await move_tool.execute(
                user_id=user_id,
                params={"source_path": str(test_file), "dest_path": str(moved_file)},
                db=session,
            )
            assert move_res.success is True
            assert not test_file.exists()
            assert moved_file.exists()

        # 5. Delete file (triggers pre-snapshot)
        async with session_factory() as session:
            del_res = await del_tool.execute(
                user_id=user_id,
                params={"path": str(moved_file)},
                db=session,
            )
            assert del_res.success is True
            assert del_res.snapshot_id is not None
            assert not moved_file.exists()


# ==============================================================================
# 3. Terminal Execution Tool & Engineering Safeguards
# ==============================================================================


@pytest.mark.asyncio
async def test_terminal_tool_allowlist_and_execution(test_user: str):
    session_factory = get_session_factory()
    user_id = test_user
    term_tool = TerminalExecuteTool()

    async with session_factory() as session:
        await grant_permission(session, user_id, "terminal.execute", "*")

    # Allowed command: echo
    async with session_factory() as session:
        res = await term_tool.execute(
            user_id=user_id,
            params={"command": ["echo", "nexus-phase-11"]},
            db=session,
        )
        assert res.success is True
        assert "nexus-phase-11" in res.output.stdout

    # Disallowed binary: sudo / nmap
    async with session_factory() as session:
        bad_res = await term_tool.execute(
            user_id=user_id,
            params={"command": ["sudo", "ls"]},
            db=session,
        )
        assert bad_res.success is False
        assert bad_res.error is not None
        assert "allowlist" in bad_res.error.lower()

    # Shell injection rejection
    async with session_factory() as session:
        inject_res = await term_tool.execute(
            user_id=user_id,
            params={"command": "echo hello; rm -rf /"},
            db=session,
        )
        assert inject_res.success is False
        assert inject_res.error is not None
        assert "injection" in inject_res.error.lower() or "unallowed" in inject_res.error.lower()


@pytest.mark.asyncio
async def test_terminal_tool_cwd_path_validation(test_user: str):
    """Safeguard 1: CWD must not target protected system directories."""
    session_factory = get_session_factory()
    user_id = test_user
    term_tool = TerminalExecuteTool()

    async with session_factory() as session:
        await grant_permission(session, user_id, "terminal.execute", "*")

    # Protected root directory
    async with session_factory() as session:
        res_root = await term_tool.execute(
            user_id=user_id,
            params={"command": ["ls"], "cwd": "/etc"},
            db=session,
        )
        assert res_root.success is False
        assert res_root.error is not None
        assert "protected" in res_root.error.lower()

    # Protected System directory
    async with session_factory() as session:
        res_sys = await term_tool.execute(
            user_id=user_id,
            params={"command": ["ls"], "cwd": "/System"},
            db=session,
        )
        assert res_sys.success is False
        assert res_sys.error is not None
        assert "protected" in res_sys.error.lower()

    # Helper function unit tests
    assert is_protected_directory("/") is True
    assert is_protected_directory("/etc") is True
    assert is_protected_directory("/System") is True
    assert is_protected_directory("/var/log") is True
    assert is_protected_directory(Path.home().as_posix()) is False


@pytest.mark.asyncio
async def test_terminal_tool_buffer_cap_and_timeout(test_user: str):
    """Safeguard 2: Stdout buffer capped at 100 KB and timeouts strictly enforced."""
    session_factory = get_session_factory()
    user_id = test_user
    term_tool = TerminalExecuteTool()

    async with session_factory() as session:
        await grant_permission(session, user_id, "terminal.execute", "*")

    # Buffer Cap Verification (> 100 KB output)
    async with session_factory() as session:
        res = await term_tool.execute(
            user_id=user_id,
            params={
                "command": [
                    sys.executable,
                    "-c",
                    f"import sys; sys.stdout.write('A' * ({MAX_COMMAND_OUTPUT_BYTES} + 1024))",
                ]
            },
            db=session,
        )
        assert res.success is True
        assert res.output.truncated is True
        assert "[Output truncated at 100 KB]" in res.output.stdout
        # Effective text before suffix should not exceed buffer limit
        assert len(res.output.stdout.split("\n[Output truncated")[0]) <= MAX_COMMAND_OUTPUT_BYTES

    # Timeout Enforcement
    async with session_factory() as session:
        res_timeout = await term_tool.execute(
            user_id=user_id,
            params={
                "command": [
                    sys.executable,
                    "-c",
                    "import time; time.sleep(5)",
                ],
                "timeout_seconds": 1.0,
            },
            db=session,
        )
        assert res_timeout.success is False
        assert res_timeout.error is not None
        assert "timed out" in res_timeout.error.lower()


# ==============================================================================
# 4. Application & Browser Tools
# ==============================================================================


@pytest.mark.asyncio
async def test_application_and_browser_tools(test_user: str):
    session_factory = get_session_factory()
    user_id = test_user
    browser_tool = BrowserOpenUrlTool()
    app_tool = ApplicationOpenTool()

    # Invalid URL scheme rejected at pydantic validation
    async with session_factory() as session:
        invalid_url = await browser_tool.execute(
            user_id=user_id,
            params={"url": "javascript:alert(1)"},
            db=session,
        )
        assert invalid_url.success is False
        assert invalid_url.error is not None
        assert "http" in invalid_url.error.lower()

    # Application name injection rejected at pydantic validation
    async with session_factory() as session:
        invalid_app = await app_tool.execute(
            user_id=user_id,
            params={"app_name": "Safari; rm -rf /"},
            db=session,
        )
        assert invalid_app.success is False
        assert invalid_app.error is not None
        assert "invalid" in invalid_app.error.lower()


# ==============================================================================
# 5. ComputerAgent & Resumable Approval Metadata
# ==============================================================================


@pytest.mark.asyncio
async def test_computer_agent_execution_and_resumable_approval(test_user: str):
    """Safeguard 3: When a tool halts with REQUIRES_APPROVAL, approval metadata is preserved."""
    session_factory = get_session_factory()
    user_id = test_user
    agent = ComputerAgent()

    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "agent_file.txt"

        step_write = PlanStep(
            id="step_write_1",
            index=1,
            description="Write initial configuration file",
            required_tools=["filesystem.write"],
            input={"path": str(test_file), "content": "config_v1"},
        )

        # Stage 1: Without permission, tool execution halts and returns approval metadata
        async with session_factory() as session:
            result_halt = await agent.run(
                step=step_write,
                context={"task_id": "task_123"},
                user_id=user_id,
                db=session,
            )
            assert result_halt.success is False
            assert result_halt.result_payload["is_awaiting_approval"] is True
            assert result_halt.result_payload["approval_id"].startswith("appr_")
            assert result_halt.result_payload["target_tool"] == "filesystem.write"
            assert result_halt.result_payload["parameters"]["path"] == str(test_file)

        # Stage 2: Grant permission and resume step execution seamlessly
        async with session_factory() as session:
            await grant_permission(session, user_id, "filesystem.write", "*")

        async with session_factory() as session:
            result_resumed = await agent.run(
                step=step_write,
                context={"task_id": "task_123"},
                user_id=user_id,
                db=session,
            )
            assert result_resumed.success is True
            assert result_resumed.result_payload["tool"] == "filesystem.write"
            assert test_file.exists()
            assert test_file.read_text() == "config_v1"


# ==============================================================================
# 6. REST API Endpoints (/api/v1/tools)
# ==============================================================================


@pytest.mark.asyncio
async def test_api_tools_endpoints(auth_user):
    client = auth_user["client"]
    headers = auth_user["headers"]
    user_id = auth_user["user_id"]
    session_factory = get_session_factory()

    # 1. List tools
    list_res = await client.get("/api/v1/tools", headers=headers)
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["total"] >= 8
    tool_names = [t["name"] for t in data["items"]]
    assert "filesystem.read" in tool_names
    assert "terminal.execute" in tool_names

    # 2. Get single tool
    get_res = await client.get("/api/v1/tools/filesystem.read", headers=headers)
    assert get_res.status_code == 200
    tool_info = get_res.json()
    assert tool_info["name"] == "filesystem.read"
    assert "properties" in tool_info["input_schema"]

    # 3. Execute tool via API without permission -> pauses for approval
    with TemporaryDirectory() as tmpdir:
        api_file = Path(tmpdir) / "api_test.txt"

        exec_res_pause = await client.post(
            "/api/v1/tools/filesystem.write/execute",
            headers=headers,
            json={
                "parameters": {
                    "path": str(api_file),
                    "content": "API execution verified!",
                }
            },
        )
        assert exec_res_pause.status_code == 200
        pause_data = exec_res_pause.json()
        assert pause_data["success"] is False
        assert pause_data["is_awaiting_approval"] is True
        assert pause_data["approval_id"] is not None

        # Now grant permission and execute again
        async with session_factory() as session:
            await grant_permission(session, user_id, "filesystem.write", "*")

        exec_res_allowed = await client.post(
            "/api/v1/tools/filesystem.write/execute",
            headers=headers,
            json={
                "parameters": {
                    "path": str(api_file),
                    "content": "API execution verified!",
                }
            },
        )
        assert exec_res_allowed.status_code == 200
        allowed_data = exec_res_allowed.json()
        assert allowed_data["success"] is True
        assert api_file.read_text() == "API execution verified!"


# ==============================================================================
# 7. MacOSAdapter Direct Operations
# ==============================================================================


@pytest.mark.asyncio
async def test_macos_adapter_direct():
    adapter = MacOSAdapter()

    with TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "adapter_test.txt"

        # Write
        w = await adapter.write_file(str(file_path), "adapter content")
        assert w["status"] == "success"

        # Read
        r = await adapter.read_file(str(file_path))
        assert r == "adapter content"

        # List dir
        listing = await adapter.list_dir(tmpdir)
        assert len(listing) == 1
        assert listing[0]["name"] == "adapter_test.txt"

        # Delete
        d = await adapter.delete_file(str(file_path))
        assert d["status"] == "success"
        assert not file_path.exists()
