"""Unit and Integration Tests for Reversible Actions, Snapshots, Diff Previews, and Rollback Mechanics."""

import hashlib
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from httpx import ASGITransport, AsyncClient

from packages.shared.nexus_shared.errors import StateConflictError
from packages.shared.nexus_shared.reversal import (
    MAX_INLINE_SIZE,
    SnapshotManager,
    compute_sha256,
    is_binary_bytes,
)
from services.api.nexus_api.database import get_session_factory, init_database
from services.api.nexus_api.main import app


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_database()


def random_email() -> str:
    return f"reversal_test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
async def auth_user_a():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = random_email()
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Password123!",
                "full_name": "Reversal User Alpha",
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
async def auth_user_b():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = random_email()
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Password123!",
                "full_name": "Reversal User Beta",
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


# ==============================================================================
# 1. Unit Tests: Action Classification & Diff Generation
# ==============================================================================


def test_action_classification():
    with TemporaryDirectory() as tmpdir:
        existing_file = Path(tmpdir) / "test.txt"
        existing_file.write_text("hello")
        non_existing = Path(tmpdir) / "new.txt"

        # File Create
        cat, rev = SnapshotManager.classify_action("filesystem.write", {"path": str(non_existing)})
        assert cat == "FILE_CREATE"
        assert rev is True

        # File Modify
        cat, rev = SnapshotManager.classify_action("filesystem.write", {"path": str(existing_file)})
        assert cat == "FILE_MODIFY"
        assert rev is True

        # File Delete
        cat, rev = SnapshotManager.classify_action(
            "filesystem.delete", {"path": str(existing_file)}
        )
        assert cat == "FILE_DELETE"
        assert rev is True

        # Terminal Execution (Never reversible)
        cat, rev = SnapshotManager.classify_action(
            "terminal.execute", {"command": "rm -rf /tmp/foo"}
        )
        assert cat == "COMMAND_EXECUTE"
        assert rev is False

        # Browser / Network mutation (Non-reversible)
        cat, rev = SnapshotManager.classify_action(
            "browser.navigate", {"url": "https://example.com"}
        )
        assert cat == "EXTERNAL_MUTATION"
        assert rev is False


def test_generate_diff():
    diff = SnapshotManager.generate_diff(
        "line1\nline2\n", "line1\nline2_modified\nline3\n", "file.txt"
    )
    added, removed = SnapshotManager.count_diff_lines(diff)
    assert "+line2_modified" in diff
    assert "-line2" in diff
    assert added >= 1
    assert removed >= 1


# ==============================================================================
# 2. Filesystem Safeguards: Binary & Size Limits
# ==============================================================================


def test_binary_and_size_limits():
    # Binary detection
    assert is_binary_bytes(b"hello \x00 world") is True
    assert is_binary_bytes(b"hello world UTF-8 text") is False

    with TemporaryDirectory() as tmpdir:
        # Binary file snapshot
        bin_path = Path(tmpdir) / "image.bin"
        bin_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00"
        bin_path.write_bytes(bin_content)

        state = SnapshotManager.capture_pre_state(str(bin_path))
        assert state["exists"] is True
        assert state["is_binary"] is True
        assert state["content"] is None
        assert state["sha256"] == hashlib.sha256(bin_content).hexdigest()

        # Oversized file (> 1MB)
        large_path = Path(tmpdir) / "large.txt"
        large_content = "A" * (MAX_INLINE_SIZE + 100)
        large_path.write_text(large_content)

        large_state = SnapshotManager.capture_pre_state(str(large_path))
        assert large_state["exists"] is True
        assert large_state["is_oversized"] is True
        assert large_state["content"] is None
        assert large_state["sha256"] == hashlib.sha256(large_content.encode("utf-8")).hexdigest()


# ==============================================================================
# 3. Snapshot Lifecycle & Rollback Mechanics
# ==============================================================================


@pytest.mark.asyncio
async def test_revert_file_create():
    """Reverting a FILE_CREATE action must delete the created file."""
    session_factory = get_session_factory()
    user_id = str(uuid.uuid4())

    with TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "created_file.txt"
        target.write_text("brand new content")

        async with session_factory() as session:
            snapshot = await SnapshotManager.create_snapshot(
                session=session,
                user_id=user_id,
                capability_name="filesystem.write",
                action_type="FILE_CREATE",
                target_path=str(target),
                auto_apply=True,
                before_state={"exists": False, "content": None, "sha256": None},
                after_state={
                    "exists": True,
                    "content": "brand new content",
                    "sha256": compute_sha256("brand new content"),
                },
                diff_patch="@@ -0,0 +1 @@\n+brand new content",
            )
            snapshot_id = snapshot.id

        assert target.exists()

        # Execute rollback
        async with session_factory() as session:
            res = await SnapshotManager.revert_action(
                session=session,
                snapshot_id=snapshot_id,
                user_id=user_id,
            )
            assert res.status == "REVERTED"

        # Target file must now be deleted
        assert not target.exists()


@pytest.mark.asyncio
async def test_revert_file_modify():
    """Reverting a FILE_MODIFY action must restore the original content."""
    session_factory = get_session_factory()
    user_id = str(uuid.uuid4())

    with TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "modify_file.txt"
        original_content = "Original version 1"
        modified_content = "Modified version 2"

        target.write_text(modified_content)

        async with session_factory() as session:
            snapshot = await SnapshotManager.create_snapshot(
                session=session,
                user_id=user_id,
                capability_name="filesystem.write",
                action_type="FILE_MODIFY",
                target_path=str(target),
                auto_apply=True,
                before_state={
                    "exists": True,
                    "content": original_content,
                    "sha256": compute_sha256(original_content),
                },
                after_state={
                    "exists": True,
                    "content": modified_content,
                    "sha256": compute_sha256(modified_content),
                },
                diff_patch="@@ -1 +1 @@\n-Original version 1\n+Modified version 2",
            )
            snapshot_id = snapshot.id

        assert target.read_text() == modified_content

        # Execute rollback
        async with session_factory() as session:
            res = await SnapshotManager.revert_action(
                session=session,
                snapshot_id=snapshot_id,
                user_id=user_id,
            )
            assert res.status == "REVERTED"

        assert target.read_text() == original_content


@pytest.mark.asyncio
async def test_revert_file_delete_and_safe_directory_creation():
    """Reverting a FILE_DELETE must recreate missing parent directories and restore the file."""
    session_factory = get_session_factory()
    user_id = str(uuid.uuid4())

    with TemporaryDirectory() as tmpdir:
        nested_dir = Path(tmpdir) / "deep" / "nested" / "dir"
        target = nested_dir / "document.md"
        content = "# Recovered Document\nAll data is preserved."

        # Simulate deletion of file and removal of directory hierarchy
        async with session_factory() as session:
            snapshot = await SnapshotManager.create_snapshot(
                session=session,
                user_id=user_id,
                capability_name="filesystem.delete",
                action_type="FILE_DELETE",
                target_path=str(target),
                auto_apply=True,
                before_state={
                    "exists": True,
                    "content": content,
                    "sha256": compute_sha256(content),
                },
                after_state={"exists": False, "content": None, "sha256": None},
                diff_patch="@@ -1,2 +0,0 @@\n-# Recovered Document\n-All data is preserved.",
            )
            snapshot_id = snapshot.id

        assert not target.exists()
        assert not nested_dir.exists()

        # Rollback
        async with session_factory() as session:
            res = await SnapshotManager.revert_action(
                session=session,
                snapshot_id=snapshot_id,
                user_id=user_id,
            )
            assert res.status == "REVERTED"

        assert target.exists()
        assert target.read_text() == content


# ==============================================================================
# 4. State Drift Detection Safeguard
# ==============================================================================


@pytest.mark.asyncio
async def test_drift_detection_conflict_and_force():
    """Rollback must detect intermediate modifications and throw StateConflictError unless force=True."""
    session_factory = get_session_factory()
    user_id = str(uuid.uuid4())

    with TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "drift.txt"
        v1_content = "v1 initial"
        v2_content = "v2 modified by action"
        v3_drift_content = "v3 modified by external user while agent was running"

        # File was modified to v2
        target.write_text(v2_content)

        async with session_factory() as session:
            snapshot = await SnapshotManager.create_snapshot(
                session=session,
                user_id=user_id,
                capability_name="filesystem.write",
                action_type="FILE_MODIFY",
                target_path=str(target),
                auto_apply=True,
                before_state={
                    "exists": True,
                    "content": v1_content,
                    "sha256": compute_sha256(v1_content),
                },
                after_state={
                    "exists": True,
                    "content": v2_content,
                    "sha256": compute_sha256(v2_content),
                },
            )
            snapshot_id = snapshot.id

        # External drift occurs!
        target.write_text(v3_drift_content)

        # Attempt revert without force -> MUST raise StateConflictError
        async with session_factory() as session:
            with pytest.raises(StateConflictError) as exc_info:
                await SnapshotManager.revert_action(
                    session=session,
                    snapshot_id=snapshot_id,
                    user_id=user_id,
                    force=False,
                )
            assert "drift detected" in str(exc_info.value).lower()

        # File must remain undisturbed at v3
        assert target.read_text() == v3_drift_content

        # Revert with force=True -> succeeds and overwrites to v1
        async with session_factory() as session:
            res = await SnapshotManager.revert_action(
                session=session,
                snapshot_id=snapshot_id,
                user_id=user_id,
                force=True,
            )
            assert res.status == "REVERTED"

        assert target.read_text() == v1_content


@pytest.mark.asyncio
async def test_non_reversible_action_revert_rejected():
    """Attempting to revert non-reversible actions must fail."""
    session_factory = get_session_factory()
    user_id = str(uuid.uuid4())

    async with session_factory() as session:
        snapshot = await SnapshotManager.create_snapshot(
            session=session,
            user_id=user_id,
            capability_name="terminal.execute",
            action_type="COMMAND_EXECUTE",
            is_reversible=False,
        )
        snapshot_id = snapshot.id

    async with session_factory() as session:
        with pytest.raises(ValueError) as exc_info:
            await SnapshotManager.revert_action(
                session=session,
                snapshot_id=snapshot_id,
                user_id=user_id,
            )
        assert "non-reversible" in str(exc_info.value).lower()


# ==============================================================================
# 5. REST API Integration Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_api_diff_preview(auth_user_a):
    client = auth_user_a["client"]
    headers = auth_user_a["headers"]

    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "diff_test.py"
        test_file.write_text("def hello():\n    return 'world'\n")

        response = await client.post(
            "/api/v1/reversal/diff/preview",
            headers=headers,
            json={
                "target_path": str(test_file),
                "proposed_content": "def hello():\n    return 'nexus'\n",
                "action_type": "FILE_MODIFY",
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["is_reversible"] is True
        assert "-    return 'world'" in data["diff_patch"]
        assert "+    return 'nexus'" in data["diff_patch"]
        assert data["lines_added"] >= 1
        assert data["lines_removed"] >= 1


@pytest.mark.asyncio
async def test_api_snapshots_list_and_tenant_isolation(auth_user_a, auth_user_b):
    client_a = auth_user_a["client"]
    headers_a = auth_user_a["headers"]
    user_a_id = auth_user_a["user_id"]

    client_b = auth_user_b["client"]
    headers_b = auth_user_b["headers"]

    session_factory = get_session_factory()

    with TemporaryDirectory() as tmpdir:
        file_a = Path(tmpdir) / "alpha.txt"
        file_a.write_text("alpha content")

        async with session_factory() as session:
            snap_a = await SnapshotManager.create_snapshot(
                session=session,
                user_id=user_a_id,
                capability_name="filesystem.write",
                action_type="FILE_MODIFY",
                target_path=str(file_a),
                auto_apply=True,
                before_state={
                    "exists": True,
                    "content": "initial",
                    "sha256": compute_sha256("initial"),
                },
                after_state={
                    "exists": True,
                    "content": "alpha content",
                    "sha256": compute_sha256("alpha content"),
                },
            )
            snapshot_id = snap_a.id

        # User A can list snapshots
        list_res = await client_a.get("/api/v1/reversal/snapshots", headers=headers_a)
        assert list_res.status_code == 200
        items = list_res.json()["items"]
        assert any(item["id"] == snapshot_id for item in items)

        # User A can get snapshot by ID
        get_res = await client_a.get(f"/api/v1/reversal/snapshots/{snapshot_id}", headers=headers_a)
        assert get_res.status_code == 200
        assert get_res.json()["id"] == snapshot_id

        # User B cannot get or revert User A's snapshot (Tenant Isolation)
        get_b = await client_b.get(f"/api/v1/reversal/snapshots/{snapshot_id}", headers=headers_b)
        assert get_b.status_code == 404

        revert_b = await client_b.post(
            f"/api/v1/reversal/snapshots/{snapshot_id}/revert",
            headers=headers_b,
            json={"force": False},
        )
        assert revert_b.status_code == 404

        # User A can revert their snapshot
        revert_a = await client_a.post(
            f"/api/v1/reversal/snapshots/{snapshot_id}/revert",
            headers=headers_a,
            json={"force": False},
        )
        assert revert_a.status_code == 200, revert_a.text
        assert revert_a.json()["status"] == "REVERTED"
        assert file_a.read_text() == "initial"


@pytest.mark.asyncio
async def test_api_revert_conflict_and_force(auth_user_a):
    client = auth_user_a["client"]
    headers = auth_user_a["headers"]
    user_id = auth_user_a["user_id"]
    session_factory = get_session_factory()

    with TemporaryDirectory() as tmpdir:
        drift_file = Path(tmpdir) / "drift_api.txt"
        v1 = "initial 1"
        v2 = "modified 2"
        v3 = "external drift 3"

        drift_file.write_text(v2)

        async with session_factory() as session:
            snap = await SnapshotManager.create_snapshot(
                session=session,
                user_id=user_id,
                capability_name="filesystem.write",
                action_type="FILE_MODIFY",
                target_path=str(drift_file),
                auto_apply=True,
                before_state={
                    "exists": True,
                    "content": v1,
                    "sha256": compute_sha256(v1),
                },
                after_state={
                    "exists": True,
                    "content": v2,
                    "sha256": compute_sha256(v2),
                },
            )
            snapshot_id = snap.id

        # Cause drift
        drift_file.write_text(v3)

        # Revert without force -> 409 Conflict
        conflict_res = await client.post(
            f"/api/v1/reversal/snapshots/{snapshot_id}/revert",
            headers=headers,
            json={"force": False},
        )
        assert conflict_res.status_code == 409
        assert "drift detected" in conflict_res.json()["detail"].lower()
        assert drift_file.read_text() == v3

        # Revert with force -> 200 OK and restores v1
        force_res = await client.post(
            f"/api/v1/reversal/snapshots/{snapshot_id}/revert",
            headers=headers,
            json={"force": True},
        )
        assert force_res.status_code == 200, force_res.text
        assert force_res.json()["status"] == "REVERTED"
        assert drift_file.read_text() == v1
